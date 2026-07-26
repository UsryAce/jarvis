import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from "axios";

export type TrustScope =
  | "operator.read"
  | "runs.control"
  | "emergency.stop"
  | "secrets.admin"
  | "voice.use"
  | string;

export interface SessionSnapshot {
  authenticated: true;
  actor_id: string;
  scopes: TrustScope[];
  csrf_token: string;
  expires_at: string;
}

export interface SafeApiError {
  code:
    | "authentication_required"
    | "wrong_scope"
    | "csrf_invalid"
    | "stale_revision"
    | "stale_version"
    | "offline"
    | "ambiguous_timeout"
    | string;
  correlation_id?: string;
  audit_id?: string;
  retryable: boolean;
  applied: boolean | null;
}

export class SafeApiException extends Error {
  readonly safe: SafeApiError;
  readonly status?: number;

  constructor(safe: SafeApiError, status?: number) {
    super(safe.code);
    this.name = "SafeApiException";
    this.safe = safe;
    this.status = status;
  }
}

export type ControlState =
  | "operational"
  | "accepted"
  | "pausing"
  | "paused"
  | "cancelling"
  | "stopping"
  | "stopped"
  | "partial"
  | "unconfirmed"
  | "integrity_locked";

export type ControlAction = "pause" | "cancel" | "emergency_stop" | "reset";

export interface ControlSnapshot {
  scope_type: "global" | "run";
  scope_id: string;
  state: ControlState;
  revision: number;
  requested_at: string;
  updated_at: string;
  reason_code: string;
  confirmed_count: number;
  total_count: number;
  residue_count: number;
  allowed_actions: ControlAction[];
  audit_id: string | null;
}

export interface ControlMutation {
  action: ControlAction;
  scope_type: "global" | "run";
  scope_id: string;
  expected_revision: number;
  client_request_id: string;
  reason_code?: string;
  reauthentication_credential?: string;
}

export type CredentialLifecycleState =
  | "pending_validation"
  | "valid"
  | "active"
  | "draining"
  | "disabled"
  | "invalid"
  | "indeterminate"
  | "revoked"
  | "unrecoverable";

export type CredentialValidationCategory =
  | "not_run"
  | "valid"
  | "invalid"
  | "indeterminate"
  | "unrecoverable";

export type CredentialAction =
  | "validate"
  | "promote"
  | "priority"
  | "drain"
  | "disable"
  | "rotate"
  | "revoke";

export interface CredentialObservation<T = number> {
  value: T | null;
  source: string | null;
  observed_at: string | null;
}

export interface CredentialMetadata {
  credential_id: string;
  display_id: string;
  provider: string;
  label: string;
  state: CredentialLifecycleState;
  priority: number;
  version: number;
  provider_generation: number;
  validation_category: CredentialValidationCategory;
  validated_at: string | null;
  health: CredentialObservation<string>;
  quota: CredentialObservation;
  usage: CredentialObservation;
  lease_count: number;
  replacement_display_id: string | null;
  allowed_actions: CredentialAction[];
  audit_id: string | null;
}

export interface CredentialMutation {
  action: CredentialAction;
  credential_id: string;
  expected_version: number;
  client_request_id: string;
  label?: string;
  priority?: number;
  provider?: string;
  secret?: string;
}

export type MutationOutcome<T> =
  | { status: "authoritative"; value: T }
  | {
      status: "reconcile_required";
      reason: "stale" | "ambiguous" | "csrf";
      error: SafeApiError;
      authoritative: T | T[] | null;
    };

type ProtectedTransportResetReason = "unauthorized" | "logout" | "manual";
type ProtectedTransportResetListener = (
  reason: ProtectedTransportResetReason,
) => void;

let csrfToken: string | null = null;
const protectedTransportResetListeners = new Set<ProtectedTransportResetListener>();

export function setCsrfToken(token: string): void {
  csrfToken = token;
}

export function clearProtectedTransportState(
  reason: ProtectedTransportResetReason = "manual",
): void {
  csrfToken = null;
  protectedTransportResetListeners.forEach((listener) => listener(reason));
}

export function onProtectedTransportReset(
  listener: ProtectedTransportResetListener,
): () => void {
  protectedTransportResetListeners.add(listener);
  return () => protectedTransportResetListeners.delete(listener);
}

const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

function attachCsrfHeader(config: InternalAxiosRequestConfig) {
  if (csrfToken && UNSAFE_METHODS.has((config.method || "get").toLowerCase())) {
    config.headers.set("X-Jarvis-CSRF", csrfToken);
  }
  return config;
}

function isSafeApiError(value: unknown): value is SafeApiError {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    (candidate.correlation_id === undefined ||
      typeof candidate.correlation_id === "string") &&
    (candidate.audit_id === undefined || candidate.audit_id === null ||
      typeof candidate.audit_id === "string") &&
    typeof candidate.retryable === "boolean" &&
    (candidate.applied === null || typeof candidate.applied === "boolean")
  );
}

function safeExceptionFromAxios(error: AxiosError): SafeApiException {
  const unsafeMethod = UNSAFE_METHODS.has(
    (error.config?.method || "get").toLowerCase(),
  );
  if (isSafeApiError(error.response?.data)) {
    return new SafeApiException(error.response.data, error.response?.status);
  }
  const timedOut = error.code === "ECONNABORTED" || error.code === "ETIMEDOUT";
  return new SafeApiException(
    {
      code: timedOut && unsafeMethod ? "ambiguous_timeout" : "offline",
      retryable: !unsafeMethod,
      applied: unsafeMethod ? null : false,
    },
    error.response?.status,
  );
}

class APIClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor(baseURL: string = "") {
    this.baseURL = baseURL;

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 120000,
      withCredentials: true,
      headers: {
        "Content-Type": "application/json",
      },
    });

    this.client.interceptors.request.use(attachCsrfHeader);

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          clearProtectedTransportState("unauthorized");
        }
        return Promise.reject(safeExceptionFromAxios(error));
      },
    );
  }

  private fetchHeaders(method: string, contentType = true): HeadersInit {
    const headers: Record<string, string> = {};
    if (contentType) headers["Content-Type"] = "application/json";
    if (csrfToken && UNSAFE_METHODS.has(method.toLowerCase())) {
      headers["X-Jarvis-CSRF"] = csrfToken;
    }
    return headers;
  }

  private async parseSafeFetchError(
    response: Response,
    method: string,
  ): Promise<SafeApiException> {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }
    if (response.status === 401) clearProtectedTransportState("unauthorized");
    if (isSafeApiError(payload)) {
      return new SafeApiException(payload, response.status);
    }
    return new SafeApiException(
      {
        code: response.status === 403 ? "wrong_scope" : "request_rejected",
        retryable: false,
        applied: UNSAFE_METHODS.has(method.toLowerCase()) ? null : false,
      },
      response.status,
    );
  }

  private async refreshCsrf(): Promise<void> {
    const session = await this.getOperatorSession();
    setCsrfToken(session.csrf_token);
  }

  private async runMutation<T>(
    request: () => Promise<T>,
    reconcile: () => Promise<T | T[]>,
  ): Promise<MutationOutcome<T>> {
    try {
      return { status: "authoritative", value: await request() };
    } catch (error) {
      if (!(error instanceof SafeApiException)) throw error;
      const safe = error.safe;
      if (safe.code === "csrf_invalid" && safe.applied === false) {
        await this.refreshCsrf();
        try {
          return { status: "authoritative", value: await request() };
        } catch (retryError) {
          if (!(retryError instanceof SafeApiException)) throw retryError;
          return {
            status: "reconcile_required",
            reason: "csrf",
            error: retryError.safe,
            authoritative: await reconcile().catch(() => null),
          };
        }
      }
      if (
        safe.code === "stale_revision" ||
        safe.code === "stale_version" ||
        safe.code === "csrf_invalid" ||
        safe.code === "ambiguous_timeout" ||
        safe.applied === null
      ) {
        return {
          status: "reconcile_required",
          reason: safe.code.startsWith("stale_") ? "stale" : "ambiguous",
          error: safe,
          authoritative: await reconcile().catch(() => null),
        };
      }
      throw error;
    }
  }

  async unlock(credential: string): Promise<SessionSnapshot> {
    const response = await this.client.post<SessionSnapshot>("/api/auth/unlock", {
      credential,
    });
    setCsrfToken(response.data.csrf_token);
    return response.data;
  }

  async getOperatorSession(): Promise<SessionSnapshot> {
    const response = await this.client.get<SessionSnapshot>("/api/auth/session");
    setCsrfToken(response.data.csrf_token);
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.post("/api/auth/logout");
    } finally {
      clearProtectedTransportState("logout");
    }
  }

  async getControl(
    scopeType: "global" | "run" = "global",
    scopeId = "global",
  ): Promise<ControlSnapshot> {
    const response = await this.client.get<ControlSnapshot>("/api/control", {
      params: { scope_type: scopeType, scope_id: scopeId },
    });
    return response.data;
  }

  async mutateControl(
    mutation: ControlMutation,
  ): Promise<MutationOutcome<ControlSnapshot>> {
    const path = mutation.action.replace("_", "-");
    const payload: Record<string, unknown> = {
      scope_type: mutation.scope_type,
      scope_id: mutation.scope_id,
      expected_revision: mutation.expected_revision,
      client_request_id: mutation.client_request_id,
      reason_code: mutation.reason_code || "operator_requested",
    };
    if (mutation.action === "reset") {
      payload.reauthentication_credential = mutation.reauthentication_credential;
    }
    return this.runMutation(
      async () =>
        (await this.client.post<ControlSnapshot>(`/api/control/${path}`, payload))
          .data,
      () => this.getControl(mutation.scope_type, mutation.scope_id),
    );
  }

  async listCredentials(): Promise<CredentialMetadata[]> {
    const response = await this.client.get<
      CredentialMetadata[] | { credentials: CredentialMetadata[] }
    >("/api/credentials");
    return Array.isArray(response.data) ? response.data : response.data.credentials;
  }

  async addCredential(input: {
    provider: string;
    label: string;
    secret: string;
    client_request_id: string;
  }): Promise<MutationOutcome<CredentialMetadata>> {
    return this.runMutation(
      async () =>
        (await this.client.post<CredentialMetadata>("/api/credentials", input)).data,
      () => this.listCredentials(),
    );
  }

  async transitionCredential(
    mutation: CredentialMutation,
  ): Promise<MutationOutcome<CredentialMetadata>> {
    const { action, credential_id, ...payload } = mutation;
    return this.runMutation(
      async () =>
        (
          await this.client.post<CredentialMetadata>(
            `/api/credentials/${encodeURIComponent(credential_id)}/${action}`,
            payload,
          )
        ).data,
      () => this.listCredentials(),
    );
  }

  // Chat API
  async chat(
    message: string,
    options?: {
      model?: string;
      stream?: boolean;
      useMemory?: boolean;
      useSkills?: boolean;
      maxTokens?: number;
      systemPrompt?: string;
    },
  ) {
    const response = await this.client.post("/api/chat", {
      message,
      model: options?.model,
      stream: options?.stream ?? false,
      use_memory: options?.useMemory ?? true,
      use_skills: options?.useSkills ?? true,
      max_tokens: options?.maxTokens ?? 1024,
    });
    return response.data as {
      response: string;
      model: string;
      task_category: string;
      routing_reason: string;
      auto_mode: boolean;
    };
  }

  async chatStream(
    message: string,
    onChunk: (chunk: string) => void,
    options?: Record<string, unknown>,
  ) {
    const requestedModel = String(options?.model || "auto");
    const fallbackModel = "meta/llama-3.1-8b-instruct";
    const canFallback =
      requestedModel === "auto" || requestedModel === "z-ai/glm-5.2";

    const run = async (model: string, firstTokenTimeoutMs: number) => {
      const controller = new AbortController();
      let receivedContent = false;
      const firstTokenTimer = window.setTimeout(
        () => controller.abort("first-token-timeout"),
        firstTokenTimeoutMs,
      );
      try {
        const response = await fetch(`${this.baseURL}/api/chat`, {
          method: "POST",
          headers: this.fetchHeaders("POST"),
          credentials: "include",
          body: JSON.stringify({ message, ...options, model, stream: true }),
          signal: controller.signal,
        });

        if (!response.ok) throw await this.parseSafeFetchError(response, "POST");
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let metadata: Record<string, any> = {};

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split("\n\n");
            buffer = events.pop() || "";
            for (const event of events) {
              const line = event
                .split("\n")
                .find((item) => item.startsWith("data: "));
              if (!line) continue;
              try {
                const data = JSON.parse(line.slice(6));
                if (data.content) {
                  receivedContent = true;
                  window.clearTimeout(firstTokenTimer);
                  onChunk(data.content);
                }
                if (data.error) throw new Error(data.error);
                if (data.done) metadata = data;
              } catch (error) {
                if (error instanceof SyntaxError) continue;
                throw error;
              }
            }
          }
        }
        return metadata;
      } catch (error) {
        if (
          !receivedContent &&
          canFallback &&
          model !== fallbackModel &&
          error instanceof SafeApiException &&
          error.safe.applied === false
        ) {
          return run(fallbackModel, 20_000);
        }
        if (controller.signal.aborted) {
          throw new SafeApiException({
            code: "ambiguous_timeout",
            retryable: false,
            applied: null,
          });
        }
        throw error;
      } finally {
        window.clearTimeout(firstTokenTimer);
      }
    };

    return run(requestedModel, canFallback ? 5_000 : 20_000);
  }

  // Memory API
  async remember(content: string, metadata?: Record<string, any>) {
    const response = await this.client.post("/api/memory/remember", {
      content,
      metadata,
    });
    return response.data;
  }

  async recall(query: string, limit: number = 5) {
    const response = await this.client.get("/api/memory/recall", {
      params: { query, limit },
    });
    return response.data;
  }

  // Skills API
  async executeSkill(skillName: string, params: Record<string, any>) {
    const response = await this.client.post(`/api/skills/${skillName}`, {
      params,
    });
    return response.data;
  }

  async listSkills() {
    const response = await this.client.get("/api/skills");
    return response.data;
  }

  // Voice API
  async transcribe(audioBlob: Blob, language = "en-US") {
    const formData = new FormData();
    const extension = audioBlob.type.includes("ogg")
      ? "ogg"
      : audioBlob.type.includes("wav")
        ? "wav"
        : "webm";
    formData.append("file", audioBlob, `audio.${extension}`);
    formData.append("language_code", language);

    const response = await this.client.post("/api/voice/transcribe", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  }

  async synthesize(
    text: string,
    voiceName: string = "Magpie-Multilingual.EN-US.Leo.Neutral",
  ) {
    const response = await this.client.post(
      "/api/voice/synthesize-auto",
      {
        text,
        preferred_provider: "nvidia",
        voice_name: "en-GB-RyanNeural",
        nvidia_voice_name: voiceName,
        rate: "+8%",
        language_code: "en-US",
        sample_rate_hz: 22050,
      },
      { responseType: "blob", timeout: 15000 },
    );
    return this.requireAudioBlob(response.data, response.headers["content-type"]);
  }

  async synthesizeEdge(
    text: string,
    voiceName: string = "en-GB-RyanNeural",
  ) {
    const response = await this.client.post(
      "/api/voice/synthesize-edge",
      { text, voice_name: voiceName, rate: "+8%" },
      { responseType: "blob", timeout: 10000 },
    );
    return this.requireAudioBlob(response.data, response.headers["content-type"]);
  }

  async synthesizeAuto(
    text: string,
    preferredProvider: "edge" | "nvidia" = "edge",
    edgeVoiceName: string = "en-GB-RyanNeural",
    nvidiaVoiceName: string = "Magpie-Multilingual.EN-US.Leo.Neutral",
  ) {
    const response = await this.client.post(
      "/api/voice/synthesize-auto",
      {
        text,
        preferred_provider: preferredProvider,
        voice_name: edgeVoiceName,
        nvidia_voice_name: nvidiaVoiceName,
        rate: "+8%",
        language_code: "en-US",
        sample_rate_hz: 22050,
      },
      { responseType: "blob", timeout: 15000 },
    );
    return {
      audio: this.requireAudioBlob(
        response.data,
        response.headers["content-type"],
      ),
      provider: String(response.headers["x-voice-provider"] || "unknown"),
      synthesisMs: Number(response.headers["x-synthesis-ms"] || 0),
    };
  }

  async synthesizeStream(
    text: string,
    onChunk: (chunk: Uint8Array) => void,
    voiceName: string = "Magpie-Multilingual.EN-US.Leo.Neutral",
  ) {
    const response = await fetch(
      `${this.baseURL}/api/voice/synthesize-stream`,
      {
        method: "POST",
        headers: this.fetchHeaders("POST"),
        credentials: "include",
        body: JSON.stringify({
          text,
          voice_name: voiceName,
          language_code: "en-US",
          sample_rate_hz: 22050,
        }),
      },
    );
    if (!response.ok) throw await this.parseSafeFetchError(response, "POST");
    if (!response.body)
      throw new SafeApiException({
        code: "voice_stream_unavailable",
        retryable: false,
        applied: null,
      });
    const reader = response.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value?.length) onChunk(value);
    }
  }

  private requireAudioBlob(value: unknown, contentType?: unknown): Blob {
    if (!(value instanceof Blob) || value.size === 0)
      throw new Error("Voice provider returned empty audio");
    const type = typeof contentType === "string" ? contentType : value.type;
    if (!type.toLowerCase().startsWith("audio/"))
      throw new Error(`Voice provider returned ${type || "an unknown format"}`);
    return value;
  }

  // System API
  async getStatus() {
    const response = await this.client.get("/api/status");
    return response.data;
  }

  async getDashboardState() {
    const response = await this.client.get("/api/dashboard/state");
    return response.data as {
      system?: { cpu?: number; ram?: number; gpu?: number; uptime?: string };
      [key: string]: unknown;
    };
  }

  async getSession() {
    const response = await this.client.get("/api/session");
    return response.data;
  }

  async clearSession() {
    const response = await this.client.delete("/api/session");
    return response.data;
  }

  async getBrain() {
    const response = await this.client.get("/api/brain");
    return response.data;
  }

  async searchBrain(query: string, limit = 20) {
    const response = await this.client.post("/api/brain/search", {
      query,
      limit,
    });
    return response.data;
  }

  async openBrainTarget(target: "vault" | "graph" | "report") {
    const response = await this.client.post("/api/brain/open", {
      target,
      confirm: true,
    });
    return response.data;
  }

  async getKeyStatus() {
    const response = await this.client.get("/api/keys/status");
    return response.data as { configured?: boolean; provider?: string };
  }

  async routeTask(message: string, preferredModel?: string) {
    const response = await this.client.post("/api/router/preview", {
      message,
      model: preferredModel || "auto",
    });
    return response.data as {
      model: string;
      routing_reason?: string;
      task_category?: string;
    };
  }

  async runAgent(
    goal: string,
    model = "auto",
    maxSteps = 8,
    autonomy: "guarded" | "full" = "guarded",
    projectId = "jarvis",
  ) {
    const response = await this.client.post("/api/agent/run", {
      goal,
      model,
      max_steps: maxSteps,
      autonomy,
      project_id: projectId,
      max_retries: 2,
      background: true,
    });
    return response.data as Record<string, any>;
  }

  async getAgentRuntime() {
    const response = await this.client.get("/api/agent/runtime");
    return response.data as Record<string, any>;
  }

  async getAgentRuns(limit = 50) {
    const response = await this.client.get("/api/agent/runs", {
      params: { limit },
    });
    return response.data as { runs: Array<Record<string, any>> };
  }

  async getAgentRun(id: string) {
    const response = await this.client.get(
      `/api/agent/runs/${encodeURIComponent(id)}`,
    );
    return response.data as Record<string, any>;
  }

  async approveAgentRun(id: string, stepIds: string[]) {
    const response = await this.client.post(
      `/api/agent/runs/${encodeURIComponent(id)}/approve`,
      { step_ids: stepIds },
    );
    return response.data as Record<string, any>;
  }

  async cancelAgentRun(id: string) {
    const response = await this.client.post(
      `/api/agent/runs/${encodeURIComponent(id)}/cancel`,
    );
    return response.data as Record<string, any>;
  }

  async getAgentTools() {
    const response = await this.client.get("/api/agent/tools");
    return response.data as {
      tools: Array<{
        name: string;
        description: string;
        risk: "read" | "write";
      }>;
    };
  }

  async startSwarm(
    goal: string,
    mode: "cowork" | "council" | "swarm" = "swarm",
    maxAgents = 8,
    autonomy: "guarded" | "full" = "guarded",
    projectId = "jarvis",
    maxRuntimeSeconds = 1800,
  ) {
    const response = await this.client.post("/api/swarm/run", {
      goal,
      mode,
      max_agents: Math.min(8, Math.max(2, maxAgents)),
      autonomy,
      project_id: projectId,
      max_runtime_seconds: maxRuntimeSeconds,
    });
    return response.data as Record<string, any>;
  }

  async getSwarmRun(id: string) {
    const response = await this.client.get(
      `/api/swarm/runs/${encodeURIComponent(id)}`,
    );
    return response.data as Record<string, any>;
  }

  async getSwarmRuns(limit = 20) {
    const response = await this.client.get("/api/swarm/runs", {
      params: { limit },
    });
    return response.data as { runs: Array<Record<string, any>> };
  }

  async getSwarmRuntime() {
    const response = await this.client.get("/api/swarm/runtime");
    return response.data as Record<string, any>;
  }

  async cancelSwarmRun(id: string) {
    const response = await this.client.post(
      `/api/swarm/runs/${encodeURIComponent(id)}/cancel`,
    );
    return response.data as Record<string, any>;
  }

  async getSwarmWorkspace(id: string) {
    const response = await this.client.get(
      `/api/swarm/runs/${encodeURIComponent(id)}/workspace`,
    );
    return response.data as Record<string, any>;
  }

  async integrateSwarmRun(id: string, strategy = "ff-only") {
    const response = await this.client.post(
      `/api/swarm/runs/${encodeURIComponent(id)}/integrate`,
      { strategy },
    );
    return response.data as Record<string, any>;
  }

  async rejectSwarmIntegration(id: string) {
    const response = await this.client.post(
      `/api/swarm/runs/${encodeURIComponent(id)}/reject`,
    );
    return response.data as Record<string, any>;
  }

  async getProjects() {
    const response = await this.client.get("/api/projects");
    return response.data as { projects: Array<Record<string, any>> };
  }

  async registerProject(id: string, name: string, root: string) {
    const response = await this.client.post("/api/projects", { id, name, root });
    return response.data as Record<string, any>;
  }

  async searchFiles(query: string) {
    const response = await this.client.post("/api/files/search", { query });
    return response.data;
  }

  async readFile(path: string) {
    const response = await this.client.post("/api/files/read", { path });
    return response.data;
  }

  async openFile(path: string) {
    const response = await this.client.post("/api/files/open", {
      path,
      confirm: true,
    });
    return response.data;
  }

  async createNote(content: string) {
    const response = await this.client.post("/api/notes", { content });
    return response.data;
  }

  async listNotes() {
    const response = await this.client.get("/api/notes");
    return response.data;
  }

  async deleteNote(id: string) {
    const response = await this.client.delete(
      `/api/notes/${encodeURIComponent(id)}`,
    );
    return response.data;
  }

  async listTasks() {
    const response = await this.client.get("/api/tasks");
    return response.data;
  }

  async createTask(title: string, priority = "medium") {
    const response = await this.client.post("/api/tasks", { title, priority });
    return response.data;
  }

  async updateTask(id: string, changes: Record<string, unknown>) {
    const response = await this.client.put(
      `/api/tasks/${encodeURIComponent(id)}`,
      changes,
    );
    return response.data;
  }

  async deleteTask(id: string) {
    const response = await this.client.delete(
      `/api/tasks/${encodeURIComponent(id)}`,
    );
    return response.data;
  }

  async openBrowser(url: string) {
    const response = await this.client.post("/api/browser/open", { url });
    return response.data;
  }

  async executeCode(code: string, confirm = false) {
    const response = await this.client.post("/api/code/execute", {
      code,
      confirm,
    });
    return response.data;
  }

  async saveDashboardPreferences(preferences: Record<string, unknown>) {
    const response = await this.client.put(
      "/api/dashboard/preferences",
      preferences,
    );
    return response.data;
  }

  async getNvidiaSkills(query = "", limit = 50) {
    const response = await this.client.get("/api/nvidia-skills", {
      params: { query, limit },
    });
    return response.data;
  }

  async recommendNvidiaSkills(task: string, limit = 5) {
    const response = await this.client.post("/api/nvidia-skills/recommend", {
      task,
      limit,
    });
    return response.data;
  }

  async getModels() {
    const response = await this.client.get("/api/models");
    return response.data as {
      count: number;
      provider: string;
      models: Array<{
        id: string;
        object?: string;
        created?: number;
        owned_by?: string;
      }>;
    };
  }

  async getSkills() {
    const response = await this.client.get("/api/skills");
    return response.data;
  }

  // Memory
  async getMemoryStats() {
    const response = await this.client.get("/api/memory/stats");
    return response.data;
  }

  // Health check
  async healthCheck() {
    const response = await this.client.get("/api/health");
    return response.data;
  }
}

export const api = new APIClient();

export default api;
