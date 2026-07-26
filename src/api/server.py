"""FastAPI server for Jarvis web interface."""
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from src.core.jarvis import Jarvis
from src.clients.nvidia_client import NVIDIAClient
from src.config import config
from src.api.auth_routes import router as auth_router
from src.api.control_routes import router as control_router
from src.api.credential_routes import router as credential_router
from src.api.dashboard_routes import router as dashboard_router
from src.core.audit import AuditService
from src.core.control import ControlService
from src.core.control_store import ControlStore
from src.core.credentials import CredentialService
from src.security.auth import (
    APPROVALS_WRITE,
    AuthBoundaryMiddleware,
    EMERGENCY_STOP,
    OPERATOR_EXECUTE,
    OPERATOR_READ,
    RUNS_CONTROL,
    SECRETS_ADMIN,
    VOICE_USE,
    AuthenticationError,
    AuthorizationError,
    RoutePolicy,
    SessionService,
)
from src.security.redaction import SafeError
from src.voice.nvidia_speech import (
    NvidiaSpeechAdapter,
    NvidiaSpeechError,
    NvidiaSpeechUnavailableError,
    NvidiaSpeechValidationError,
)

logger = logging.getLogger(__name__)


# Global Jarvis instance - will be initialized in lifespan
jarvis: Jarvis = None
_unconfigured_speech = NvidiaSpeechAdapter()


def _nvidia_speech_adapter() -> NvidiaSpeechAdapter:
    """Resolve the current generation-fenced adapter without plaintext config."""
    if jarvis is not None and jarvis.speech_adapter is not None:
        return jarvis.speech_adapter
    return _unconfigured_speech


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan."""
    global jarvis
    store = None
    jarvis = None
    app.state.trust_status = "starting"
    app.state.trust_failure_code = None
    try:
        # Store construction performs DACL, runtime, migration, integrity, and
        # audit verification before any consequential runtime is constructed.
        store = ControlStore(app.state.control_path)
        app.state.control_store = store
        audit_service = AuditService(
            store, protector=store.protector, clock=app.state.session_clock
        )
        app.state.audit_service = audit_service
        app.state.session_service = SessionService(store, clock=app.state.session_clock)
        app.state.credential_service = CredentialService(
            store,
            protector=store.protector,
            audit_service=audit_service,
            clock=app.state.session_clock,
        )
        control_service = ControlService(
            store, audit_service=audit_service, clock=app.state.session_clock
        )
        app.state.control_service = control_service
        jarvis = Jarvis(
            control_store=store,
            audit_service=audit_service,
            session_service=app.state.session_service,
            control_service=control_service,
            credential_service=app.state.credential_service,
        )
        app.state.jarvis = jarvis
        await jarvis.initialize()
        app.state.trust_status = (
            "ready" if jarvis._initialized else jarvis.trust_status
        )
    except Exception as exc:
        code = getattr(exc, "code", None) or (
            f"{type(exc).__name__.removesuffix('Error').casefold()}_error"
        )
        app.state.trust_status = "integrity_locked"
        app.state.trust_failure_code = str(code)[:128]
        logger.error("JARVIS trust preflight failed with safe code %s", code)
    try:
        yield
    finally:
        if jarvis is not None:
            await jarvis.shutdown()
        if store is not None:
            store.close()


app = FastAPI(
    title="JARVIS API",
    description="AI Assistant API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(auth_router)
app.include_router(control_router)
app.include_router(credential_router)
app.include_router(dashboard_router)


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    stream: bool = False
    use_memory: bool = True
    use_skills: bool = True
    max_tokens: int = 1024
    interaction_mode: str = "chat"


class ChatResponse(BaseModel):
    response: str
    model: str
    task_category: str
    routing_reason: str
    auto_mode: bool


class RouterPreviewRequest(BaseModel):
    message: str
    model: Optional[str] = "auto"


class SkillRequest(BaseModel):
    skill: str
    params: dict = {}


class RememberRequest(BaseModel):
    content: str
    metadata: dict = {}


class ExecuteSkillRequest(BaseModel):
    params: dict = {}


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=20_000)
    model: str = "auto"
    max_steps: int = Field(default=8, ge=1, le=12)
    autonomy: str = Field(default="guarded", pattern="^(guarded|full)$")
    max_retries: int = Field(default=2, ge=0, le=5)
    background: bool = True
    project_id: str = Field(default="jarvis", min_length=1, max_length=80)


class AgentApprovalRequest(BaseModel):
    step_ids: list[str] = Field(default_factory=list, max_length=12)


class AgentScheduleRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=20_000)
    next_run_at: str
    interval_seconds: Optional[int] = Field(default=None, ge=60)
    model: str = "auto"
    max_steps: int = Field(default=8, ge=1, le=12)
    autonomy: str = Field(default="guarded", pattern="^(guarded|full)$")


class SwarmRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=50_000)
    mode: str = Field(default="swarm", pattern="^(cowork|council|swarm)$")
    project_id: str = Field(default="default", min_length=1, max_length=240)
    autonomy: str = Field(default="guarded", pattern="^(guarded|full)$")
    model: str = "auto"
    max_agents: int = Field(default=8, ge=1, le=8)
    max_runtime_seconds: int = Field(default=1800, ge=60, le=7200)


class SwarmApprovalRequest(BaseModel):
    step_ids: list[str] = Field(default_factory=list, max_length=12)


class SwarmIntegrationRequest(BaseModel):
    strategy: str = Field(default="ff-only", pattern="^(ff-only|cherry-pick)$")


class ProjectWorkspaceRequest(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    root: str = Field(min_length=1, max_length=1000)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve web UI."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>JARVIS</title>
        <style>
            body { font-family: system-ui; max-width: 800px; margin: 0 auto; padding: 20px; }
            .chat { border: 1px solid #ddd; height: 400px; overflow-y: auto; padding: 10px; margin-bottom: 10px; }
            .msg { margin: 10px 0; padding: 10px; border-radius: 10px; }
            .user { background: #007bff; color: white; text-align: right; }
            .assistant { background: #f0f0f0; }
            input { width: 70%; padding: 10px; }
            button { padding: 10px 20px; }
        </style>
    </head>
    <body>
        <h1>🤖 JARVIS</h1>
        <div id="chat" class="chat"></div>
        <input id="input" placeholder="Ask JARVIS..." onkeypress="if(event.key==='Enter') send()">
        <button onclick="send()">Send</button>
        <script>
            async function send() {
                const input = document.getElementById('input');
                const msg = input.value.trim();
                if (!msg) return;
                addMessage(msg, 'user');
                input.value = '';

                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await res.json();
                addMessage(data.response, 'assistant');
            }
            function addMessage(text, type) {
                const chat = document.getElementById('chat');
                const div = document.createElement('div');
                div.className = 'msg ' + type;
                div.textContent = (type === 'user' ? 'You: ' : 'JARVIS: ') + text;
                chat.appendChild(div);
                chat.scrollTop = chat.scrollHeight;
            }
        </script>
    </body>
    </html>
    """


@app.post("/api/chat")
async def chat(request: ChatRequest, http_request: Request):
    """Chat with Jarvis."""
    routing = await jarvis.route_model(
        request.message,
        request.model,
        prefer_fast=request.interaction_mode == "voice",
    )
    max_tokens = max(1, min(request.max_tokens, 4096))
    if request.stream:
        response_stream = await jarvis.chat(
            request.message,
            stream=True,
            model=routing.model,
            use_memory=request.use_memory,
            use_skills=request.use_skills,
            max_tokens=max_tokens,
            interaction_mode=request.interaction_mode,
        )

        async def events():
            cookie = http_request.scope.get("state", {}).get("operator_cookie")
            service: SessionService = http_request.app.state.session_service
            iterator = response_stream.__aiter__()
            try:
                while True:
                    try:
                        content = await asyncio.wait_for(anext(iterator), timeout=15)
                    except TimeoutError:
                        service.recheck_transport(
                            cookie, required_scope=OPERATOR_EXECUTE
                        )
                        continue
                    except StopAsyncIteration:
                        break
                    service.recheck_transport(cookie, required_scope=OPERATOR_EXECUTE)
                    yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True, 'model': routing.model, 'task_category': routing.task_category, 'routing_reason': routing.reason, 'auto_mode': routing.auto_mode})}\n\n"
            except (AuthenticationError, AuthorizationError):
                error = SafeError(
                    code="session_ended",
                    correlation_id=str(uuid.uuid4()),
                    retryable=False,
                    applied=False,
                )
                yield f"data: {json.dumps({'error': error.to_payload()})}\n\n"
            except Exception:
                logger.error("Streaming chat failed")
                yield f"data: {json.dumps({'error': 'model_request_failed'})}\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    response = await jarvis.chat(
        request.message, model=routing.model, use_memory=request.use_memory,
        use_skills=request.use_skills, max_tokens=max_tokens,
        interaction_mode=request.interaction_mode,
    )
    return ChatResponse(
        response=response,
        model=routing.model,
        task_category=routing.task_category,
        routing_reason=routing.reason,
        auto_mode=routing.auto_mode,
    )


@app.post("/api/router/preview")
async def router_preview(request: RouterPreviewRequest):
    """Preview Auto Mode's model decision without running inference."""
    routing = await jarvis.route_model(request.message, request.model)
    return routing.to_dict()


@app.get("/api/agent/tools")
async def agent_tools():
    """List the guarded tools available to the agent runtime."""
    return {"tools": jarvis.agent_runtime.list_tools()}


@app.post("/api/agent/run")
async def agent_run(request: AgentRunRequest):
    """Persist an autonomous goal and queue it, or execute inline when requested."""
    try:
        workspace_root = jarvis.workspace_registry.resolve(request.project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project workspace is not registered") from exc
    if request.background:
        run = await jarvis.agent_runtime.submit(
            request.goal, request.model, request.max_steps, request.autonomy, request.max_retries,
            workspace_root,
        )
    else:
        run = await jarvis.agent_runtime.run(
            request.goal, request.model, request.max_steps, request.autonomy, request.max_retries,
            workspace_root,
        )
    return run.to_dict()


@app.get("/api/agent/runs")
async def agent_runs(limit: int = Query(default=50, ge=1, le=250)):
    return {"runs": jarvis.agent_runtime.list_runs(limit)}


@app.get("/api/agent/runtime")
async def agent_runtime_status():
    return jarvis.agent_runtime.status()


@app.get("/api/agent/runs/{run_id}")
async def agent_run_status(run_id: str):
    run = jarvis.agent_runtime.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run was not found")
    return run.to_dict()


@app.post("/api/agent/runs/{run_id}/approve")
async def agent_run_approve(run_id: str, request: AgentApprovalRequest):
    try:
        run = await jarvis.agent_runtime.approve(run_id, request.step_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run was not found") from exc
    return run.to_dict()


@app.post("/api/agent/runs/{run_id}/cancel")
async def agent_run_cancel(run_id: str):
    try:
        run = jarvis.agent_runtime.cancel(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run was not found") from exc
    return run.to_dict()


@app.get("/api/agent/schedules")
async def agent_schedules():
    return {"schedules": jarvis.agent_runtime.list_schedules()}


@app.post("/api/agent/schedules")
async def agent_schedule_create(request: AgentScheduleRequest):
    try:
        return jarvis.agent_runtime.create_schedule(
            request.goal, request.next_run_at, request.interval_seconds,
            request.model, request.max_steps, request.autonomy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid agent schedule") from exc


@app.delete("/api/agent/schedules/{schedule_id}")
async def agent_schedule_delete(schedule_id: str):
    try:
        jarvis.agent_runtime.delete_schedule(schedule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent schedule was not found") from exc
    return {"deleted": True, "id": schedule_id}


@app.get("/api/swarm/runtime")
async def swarm_runtime_status():
    return jarvis.swarm_runtime.status()


@app.get("/api/swarm/runs")
async def swarm_runs(limit: int = Query(default=50, ge=1, le=250)):
    return {"runs": jarvis.swarm_runtime.list_runs(limit)}


@app.post("/api/swarm/run")
async def swarm_run_create(request: SwarmRunRequest):
    try:
        project_id = "jarvis" if request.project_id in {"", "default"} else request.project_id
        jarvis.workspace_registry.get(project_id)
        run = await jarvis.swarm_runtime.submit(
            request.goal, request.mode, project_id, request.autonomy,
            request.model, request.max_agents, request.max_runtime_seconds,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project workspace is not registered") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid swarm request") from exc
    return run.to_dict()


@app.get("/api/swarm/runs/{run_id}")
async def swarm_run_status(run_id: str):
    run = jarvis.swarm_runtime.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Swarm run was not found")
    return run.to_dict()


@app.post("/api/swarm/runs/{run_id}/cancel")
async def swarm_run_cancel(run_id: str):
    try:
        return jarvis.swarm_runtime.cancel(run_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Swarm run was not found") from exc


@app.post("/api/swarm/runs/{run_id}/resume")
async def swarm_run_resume(run_id: str):
    try:
        return (await jarvis.swarm_runtime.resume(run_id)).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Swarm run was not found") from exc


@app.get("/api/swarm/runs/{run_id}/workspace")
async def swarm_run_workspace(run_id: str):
    try:
        run = jarvis.swarm_runtime.refresh_worktree(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Swarm run was not found")
    return run.to_dict()


@app.post("/api/swarm/runs/{run_id}/integrate")
async def swarm_run_integrate(run_id: str, request: SwarmIntegrationRequest):
    try:
        return (await jarvis.swarm_runtime.integrate(run_id, request.strategy)).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Swarm run was not found") from exc
    except (ValueError, RuntimeError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail="Swarm integration conflict") from exc


@app.post("/api/swarm/runs/{run_id}/reject")
async def swarm_run_integration_reject(run_id: str):
    try:
        return (await jarvis.swarm_runtime.reject_integration(run_id)).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Swarm run was not found") from exc
    except (ValueError, RuntimeError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail="Swarm integration conflict") from exc


@app.post("/api/swarm/runs/{run_id}/tasks/{task_id}/approve")
async def swarm_task_approve(run_id: str, task_id: str, request: SwarmApprovalRequest):
    run = jarvis.swarm_runtime.get_run(run_id)
    task = run.tasks.get(task_id) if run else None
    if not run or not task:
        raise HTTPException(status_code=404, detail="Swarm task was not found")
    if not task.agent_run_id:
        raise HTTPException(status_code=409, detail="Swarm task has no linked agent approval")
    agent_run = jarvis.agent_runtime.get_run(task.agent_run_id)
    if not agent_run:
        raise HTTPException(status_code=409, detail="Linked agent run was not found")
    step_ids = request.step_ids
    if not step_ids and agent_run.status == "awaiting_confirmation" and agent_run.plan:
        step_ids = [agent_run.plan.steps[agent_run.current_step].id]

    async def approve_and_resume() -> None:
        await jarvis.agent_runtime.approve(task.agent_run_id, step_ids)
        await jarvis.swarm_runtime.resume(run_id)

    asyncio.create_task(approve_and_resume())
    return {"accepted": True, "swarm_id": run_id, "task_id": task_id, "agent_run_id": task.agent_run_id}


@app.get("/api/projects")
async def project_workspaces():
    return {"projects": jarvis.workspace_registry.list()}


@app.post("/api/projects")
async def project_workspace_create(request: ProjectWorkspaceRequest):
    try:
        return jarvis.workspace_registry.register(request.id, request.name, request.root)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail="Invalid project workspace request") from exc


@app.delete("/api/projects/{project_id}")
async def project_workspace_delete(project_id: str):
    try:
        jarvis.workspace_registry.remove(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project workspace was not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail="Project workspace is in use") from exc
    return {"deleted": True, "id": project_id}


@app.get("/health")
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": getattr(app.state, "trust_status", "starting"),
        "initialized": jarvis._initialized if jarvis else False,
    }


@app.get("/api/status")
async def status():
    """Get system status."""
    if jarvis is None:
        return {
            "status": getattr(app.state, "trust_status", "integrity_locked"),
            "code": getattr(app.state, "trust_failure_code", "trust_preflight_failed"),
        }
    return jarvis.get_status()


@app.get("/api/models")
async def models():
    """Return the live NVIDIA model catalog available to this API key."""
    try:
        async with NVIDIAClient() as client:
            catalog = await client.list_models()
        items = catalog.get("data", [])
        return {"models": items, "count": len(items), "provider": "nvidia"}
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="NVIDIA model catalog is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to load NVIDIA model catalog") from exc


@app.get("/v1/models")
async def openai_compatible_models():
    """Expose the live catalog using the OpenAI-compatible NVIDIA schema."""
    try:
        async with NVIDIAClient() as client:
            return await client.list_models()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="NVIDIA model catalog is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to load NVIDIA model catalog") from exc


class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"
    rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0


class NvidiaTTSRequest(BaseModel):
    text: str
    voice_name: str = "Magpie-Multilingual.EN-US.Leo.Neutral"
    language_code: str = "en-US"
    sample_rate_hz: int = 22050
    function_name: Optional[str] = None


class EdgeTTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    voice_name: str = "en-GB-RyanNeural"
    rate: str = "+8%"


class VoiceSynthesisRequest(EdgeTTSRequest):
    """Provider-independent speech request used by the browser UI."""

    preferred_provider: Literal["edge", "nvidia"] = "edge"
    nvidia_voice_name: str = "Magpie-Multilingual.EN-US.Leo.Neutral"
    language_code: str = "en-US"
    sample_rate_hz: int = Field(default=22050, ge=8000, le=48000)


def _speech_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NvidiaSpeechValidationError):
        return HTTPException(status_code=400, detail="Invalid speech request")
    if isinstance(exc, NvidiaSpeechUnavailableError):
        return HTTPException(status_code=503, detail="NVIDIA speech is unavailable")
    return HTTPException(status_code=502, detail="NVIDIA speech request failed")


@app.get("/api/nvidia/speech/status")
async def nvidia_speech_status(probe: bool = Query(default=False)):
    adapter = _nvidia_speech_adapter()
    return await asyncio.to_thread(adapter.status, probe_catalog=probe)


@app.get("/api/nvidia/speech/capabilities")
async def nvidia_speech_capabilities():
    return _nvidia_speech_adapter().capabilities()


@app.post("/api/nvidia/speech/transcribe")
@app.post("/api/voice/transcribe")
async def nvidia_transcribe(
    file: UploadFile = File(...),
    language_code: str = Form(default="en-US"),
    function_name: Optional[str] = Form(default=None),
):
    try:
        text = await _nvidia_speech_adapter().transcribe_async(
            await file.read(),
            filename=file.filename or "audio.wav",
            language_code=language_code,
            function_name=function_name,
        )
        return {"text": text}
    except (NvidiaSpeechError, NvidiaSpeechValidationError) as exc:
        raise _speech_error(exc) from exc


@app.post("/api/nvidia/speech/synthesize")
@app.post("/api/voice/synthesize")
async def nvidia_synthesize(request: NvidiaTTSRequest):
    try:
        wav = await _nvidia_speech_adapter().synthesize_async(
            request.text,
            voice_name=request.voice_name,
            language_code=request.language_code,
            sample_rate_hz=request.sample_rate_hz,
            function_name=request.function_name,
        )
        return Response(content=wav, media_type="audio/wav")
    except (NvidiaSpeechError, NvidiaSpeechValidationError) as exc:
        raise _speech_error(exc) from exc


@app.post("/api/nvidia/speech/synthesize-stream")
@app.post("/api/voice/synthesize-stream")
async def nvidia_synthesize_stream(request: NvidiaTTSRequest, http_request: Request):
    """Stream raw PCM16 so Jarvis can start speaking before the full clip exists."""
    iterator = _nvidia_speech_adapter().synthesize_stream(
        request.text,
        voice_name=request.voice_name,
        language_code=request.language_code,
        sample_rate_hz=request.sample_rate_hz,
        function_name=request.function_name,
    )

    async def audio_chunks():
        cookie = http_request.scope.get("state", {}).get("operator_cookie")
        service: SessionService = http_request.app.state.session_service
        while True:
            service.recheck_transport(cookie, required_scope=VOICE_USE)
            chunk = await asyncio.to_thread(next, iterator, None)
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(
        audio_chunks(),
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Audio-Format": "pcm_s16le",
            "X-Sample-Rate": str(request.sample_rate_hz),
            "X-Audio-Channels": "1",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/voice/synthesize-edge")
async def edge_synthesize(request: EdgeTTSRequest):
    """Synthesize a licensed catalog voice through the keyless Edge TTS client."""
    try:
        started = time.perf_counter()
        audio = await _synthesize_edge_audio(request)
        return _audio_response(
            audio,
            media_type="audio/mpeg",
            provider="edge",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    except HTTPException:
        raise
    except TimeoutError as exc:
        logger.warning("British voice synthesis timed out")
        raise HTTPException(
            status_code=504,
            detail="British voice provider timed out; NVIDIA fallback is available",
        ) from exc
    except Exception as exc:
        logger.warning("British voice synthesis failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="British voice provider failed; NVIDIA fallback is available",
        ) from exc


async def _synthesize_edge_audio(request: EdgeTTSRequest) -> bytes:
    """Return a complete, browser-decodable MP3 with a bounded wait."""
    import edge_tts

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Speech text must not be empty")
    audio = bytearray()
    # The service is remote. A bounded wait prevents a voice request from hanging
    # indefinitely while the visual response has already completed.
    async with asyncio.timeout(8):
        communicate = edge_tts.Communicate(text, request.voice_name, rate=request.rate)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                audio.extend(chunk.get("data", b""))
    if not audio:
        raise RuntimeError("Edge TTS returned no audio")
    return bytes(audio)


def _audio_response(
    audio: bytes,
    *,
    media_type: str,
    provider: str,
    elapsed_ms: float,
) -> Response:
    """Build a non-cacheable response with transport diagnostics for the UI."""
    return Response(
        content=audio,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
            "X-Voice-Provider": provider,
            "X-Synthesis-Ms": str(round(elapsed_ms)),
        },
    )


@app.post("/api/voice/synthesize-auto")
async def synthesize_voice_auto(request: VoiceSynthesisRequest):
    """Return playable speech and transparently fail over between providers."""
    started = time.perf_counter()
    failures: list[str] = []

    async def edge_audio() -> Response:
        audio = await _synthesize_edge_audio(request)
        return _audio_response(
            audio,
            media_type="audio/mpeg",
            provider="edge",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    async def nvidia_audio() -> Response:
        wav = await _nvidia_speech_adapter().synthesize_async(
            request.text.strip(),
            voice_name=request.nvidia_voice_name,
            language_code=request.language_code,
            sample_rate_hz=request.sample_rate_hz,
        )
        return _audio_response(
            wav,
            media_type="audio/wav",
            provider="nvidia",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )

    providers = (
        (("edge", edge_audio), ("nvidia", nvidia_audio))
        if request.preferred_provider == "edge"
        else (("nvidia", nvidia_audio), ("edge", edge_audio))
    )
    for provider, synthesize in providers:
        try:
            return await synthesize()
        except Exception as exc:
            failures.append(provider)
            logger.warning("Voice provider %s failed over: %s", provider, type(exc).__name__)
    raise HTTPException(
        status_code=502,
        detail=f"Voice synthesis unavailable from providers: {', '.join(failures)}",
    )


@app.post("/api/tts")
async def tts_endpoint(request: TTSRequest):
    """Text-to-speech endpoint."""
    try:
        audio_data = await jarvis.synthesize_speech(request.text, voice=request.voice)
        from fastapi.responses import Response
        return Response(content=audio_data, media_type="audio/wav")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Text-to-speech failed") from exc


@app.get("/api/skills")
async def skills():
    """List available skills."""
    return {"skills": jarvis.get_available_skills()}


@app.post("/api/skills/{skill_name}")
async def execute_skill(skill_name: str, request: ExecuteSkillRequest):
    """Execute a skill."""
    try:
        result = await jarvis.execute_skill(skill_name, request.params)
        return {"result": result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Skill was not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Skill execution failed") from exc


@app.post("/api/memory/remember")
async def remember(request: RememberRequest):
    """Store a memory."""
    memory_id = await jarvis.remember(request.content, request.metadata)
    return {"id": memory_id}


@app.get("/api/memory/recall")
async def recall(query: str, limit: int = 5):
    """Search memories."""
    memories = await jarvis.recall(query, limit)
    return {"memories": memories}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time chat."""
    await websocket.accept()
    cookie = websocket.scope.get("state", {}).get("operator_cookie")
    service: SessionService = websocket.app.state.session_service
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=15)
            except TimeoutError:
                service.recheck_transport(cookie, required_scope=VOICE_USE)
                continue
            service.recheck_transport(cookie, required_scope=VOICE_USE)
            response = await jarvis.chat(data)
            await websocket.send_text(response)
    except (AuthenticationError, AuthorizationError):
        await websocket.close(code=4403)
    except WebSocketDisconnect:
        pass


def _configured_origins(values=None) -> tuple[str, ...]:
    configured = values
    if configured is None:
        configured = config.get("security.allowed_origins", ())
    if isinstance(configured, str):
        configured = (configured,)
    origins = tuple(dict.fromkeys(str(value) for value in configured))
    if not origins:
        raise RuntimeError("allowed_origins_required")
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise RuntimeError("allowed_origin_invalid")
    return origins


def _route_policy(path: str, methods: set[str]) -> RoutePolicy:
    if ("GET" in methods and path in {"/", "/health"}) or (
        "POST" in methods and path == "/api/auth/unlock"
    ):
        return RoutePolicy(public=True)
    long_lived = path == "/ws" or path == "/api/chat" or "synthesize-stream" in path
    if path == "/ws" or "/voice/" in path or "/nvidia/speech/" in path or path == "/api/tts":
        scope = VOICE_USE
    elif path.startswith("/api/keys") or path.startswith("/api/credentials"):
        scope = SECRETS_ADMIN
    elif "emergency" in path:
        scope = EMERGENCY_STOP
    elif "approve" in path:
        scope = APPROVALS_WRITE
    elif any(marker in path for marker in ("/cancel", "/resume", "/integrate", "/reject")):
        scope = RUNS_CONTROL
    elif methods and methods.issubset({"GET", "HEAD"}):
        scope = OPERATOR_READ
    else:
        scope = OPERATOR_EXECUTE
    return RoutePolicy(
        required_scope=scope,
        long_lived=long_lived,
        session_recheck_seconds=15 if long_lived else None,
    )


def _install_security(
    application: FastAPI,
    *,
    control_path: str | Path,
    clock,
    allowed_origins,
    initialize_store: bool,
) -> None:
    origins = _configured_origins(allowed_origins)
    application.state.control_path = Path(control_path)
    application.state.session_clock = clock or (lambda: datetime.now().astimezone())
    application.state.allowed_origins = origins
    application.state.testing = initialize_store
    for route in application.routes:
        methods = set(getattr(route, "methods", ()) or ())
        if route.__class__.__name__ == "APIWebSocketRoute":
            methods = {"WEBSOCKET"}
        route.jarvis_policy = _route_policy(route.path, methods)
    application.add_middleware(
        AuthBoundaryMiddleware,
        application=application,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Jarvis-CSRF"],
    )
    if initialize_store:
        store = ControlStore(application.state.control_path)
        application.state.control_store = store
        audit_service = AuditService(store, protector=store.protector, clock=clock)
        application.state.audit_service = audit_service
        application.state.session_service = SessionService(store, clock=clock)
        application.state.credential_service = CredentialService(
            store,
            protector=store.protector,
            audit_service=audit_service,
            clock=clock,
        )
        application.state.control_service = ControlService(
            store, audit_service=audit_service, clock=clock
        )
        application.router.on_shutdown.append(store.close)

    @application.exception_handler(RequestValidationError)
    async def safe_validation_error(_request, _exc):
        error = SafeError(
            code="invalid_request",
            correlation_id=str(uuid.uuid4()),
            retryable=False,
            applied=False,
        )
        return JSONResponse(status_code=422, content=error.to_payload())

    @application.exception_handler(Exception)
    async def safe_internal_error(_request, _exc):
        error = SafeError(
            code="internal_error",
            correlation_id=str(uuid.uuid4()),
            retryable=False,
            applied=None,
        )
        return JSONResponse(status_code=500, content=error.to_payload())


def create_app(
    *,
    control_path: str | Path | None = None,
    clock=None,
    allowed_origins=None,
    testing: bool = False,
) -> FastAPI:
    """Create an isolated real-route application for tests and embedding."""
    if control_path is None and clock is None and allowed_origins is None and not testing:
        return app
    application = FastAPI(
        title=app.title,
        description=app.description,
        version=app.version,
        lifespan=None if testing else lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.router.routes.extend(app.router.routes)
    _install_security(
        application,
        control_path=control_path or ControlStore.DEFAULT_PATH,
        clock=clock,
        allowed_origins=allowed_origins,
        initialize_store=testing,
    )
    return application


_install_security(
    app,
    control_path=ControlStore.DEFAULT_PATH,
    clock=None,
    allowed_origins=None,
    initialize_store=False,
)
