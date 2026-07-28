"""Canonical live-data contract for the Claude-designed JARVIS dashboard."""

from __future__ import annotations

import asyncio
import json
import platform
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from src.api.dashboard_routes import DATA_DIR, KNOWLEDGE, PREFERENCES_FILE, _read_preferences
from src.core.model_router import PRIMARY_MODEL
from src.models.nvidia_models import ModelType, get_models_by_type
from src.security.auth import (
    OPERATOR_EXECUTE,
    OPERATOR_READ,
    AuthenticationError,
    AuthorizationError,
    OperatorPrincipal,
    SessionService,
    require_mutation_guard,
    require_scope,
)


router = APIRouter(prefix="/api/ui", tags=["dashboard-contract"])
stream_router = APIRouter(tags=["dashboard-contract"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_STATES = {"queued", "planning", "running", "synthesizing", "executing", "testing"}
_NET_SAMPLE: tuple[float, int, int] | None = None


class UICommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_:-]+$")
    payload: dict[str, Any] | None = None


def _jarvis(request: Request):
    instance = getattr(request.app.state, "jarvis", None)
    if instance is None:
        raise HTTPException(status_code=503, detail="JARVIS is not initialized")
    return instance


def _write_preferences(updates: dict[str, Any]) -> dict[str, Any]:
    preferences = _read_preferences()
    preferences.update(updates)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = PREFERENCES_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(preferences, indent=2), encoding="utf-8")
    temporary.replace(PREFERENCES_FILE)
    return preferences


def _git_state() -> tuple[str, int]:
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"], cwd=PROJECT_ROOT,
            capture_output=True, text=True, timeout=2, check=False,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
            capture_output=True, text=True, timeout=3, check=False,
        ).stdout.splitlines()
        return branch or "detached", len(dirty)
    except (OSError, subprocess.SubprocessError):
        return "unavailable", 0


def _model_name(model_id: str) -> str:
    return model_id.rsplit("/", 1)[-1].replace("-", " ").upper()


def _model_provider(model_id: str) -> str:
    return model_id.split("/", 1)[0] if "/" in model_id else "nvidia"


def _looks_chat_compatible(model_id: str) -> bool:
    """Keep non-generative NVIDIA endpoints out of the chat model picker."""
    lowered = model_id.casefold()
    excluded = (
        "embed", "rerank", "retrieval", "parakeet", "canary", "fastpitch",
        "hifigan", "tts", "asr", "whisper", "segformer",
    )
    return not any(marker in lowered for marker in excluded)


def _model_inventory(jarvis: Any, primary: str) -> list[dict[str, Any]]:
    """Merge configured knowledge with live availability without inventing health."""
    configured = {
        model.id: model
        for model in get_models_by_type(ModelType.CHAT)
        if not model.deprecated
    }
    live = set(getattr(jarvis, "_model_catalog", set()))
    model_ids = set(configured) | live | {primary}
    rows: list[dict[str, Any]] = []
    for model_id in sorted(model_ids, key=lambda value: (value != primary, value)):
        metadata = configured.get(model_id)
        selectable = model_id in live and _looks_chat_compatible(model_id)
        rows.append({
            "id": model_id,
            "name": metadata.name if metadata else _model_name(model_id),
            "provider": _model_provider(model_id),
            "variants": 1,
            "health": "healthy" if selectable else ("down" if live else "unknown"),
            "latencyMs": 0,
            "selectable": selectable,
            "catalogSource": "live" if model_id in live else "configured",
        })
    return rows


def _gpu_percent() -> float:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        values = [float(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        return sum(values) / len(values) if values else 0.0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _network_rates() -> tuple[float, float]:
    global _NET_SAMPLE
    now = time.monotonic()
    counters = psutil.net_io_counters()
    previous, _NET_SAMPLE = _NET_SAMPLE, (now, counters.bytes_sent, counters.bytes_recv)
    if previous is None:
        return 0.0, 0.0
    elapsed = max(0.001, now - previous[0])
    return (
        max(0.0, counters.bytes_sent - previous[1]) / elapsed / 1_000_000,
        max(0.0, counters.bytes_recv - previous[2]) / elapsed / 1_000_000,
    )


def _agent_projection(agent_runs: list[dict[str, Any]], held: bool) -> tuple[str, str, str]:
    if held:
        return "paused", "Execution is held by the operator control plane.", datetime.now().isoformat()
    if not agent_runs:
        return "idle", "Ready for Ahmed's directive.", datetime.now().isoformat()
    run = agent_runs[0]
    raw = str(run.get("status", "idle"))
    state = {
        "queued": "delegating", "planning": "thinking", "running": "executing",
        "synthesizing": "thinking", "awaiting_confirmation": "awaiting_approval",
        "completed": "completed", "failed": "error", "cancelled": "paused",
    }.get(raw, "idle")
    detail = str(run.get("goal") or raw).replace("\n", " ")[:180]
    return state, detail, str(run.get("updated_at") or datetime.now().isoformat())


def _events(history: list[dict[str, Any]], agent_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in history[-8:]:
        role = str(item.get("role", "system"))
        events.append({
            "at": str(item.get("timestamp", "")),
            "who": "AHMED" if role == "user" else "JARVIS",
            "meta": role,
            "text": str(item.get("content", ""))[:600],
            "level": "info",
        })
    for run in agent_runs[:5]:
        events.append({
            "at": str(run.get("updated_at", "")), "who": "AGENT",
            "meta": f"{run.get('id', '')} · {run.get('status', '')}",
            "text": str(run.get("goal", ""))[:600],
            "level": "error" if run.get("status") == "failed" else "info",
        })
    return sorted(events, key=lambda item: item["at"])[-12:]


async def build_snapshot(request: Request) -> dict[str, Any]:
    jarvis = _jarvis(request)
    preferences = _read_preferences()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.cwd().anchor or str(PROJECT_ROOT.anchor))
    agent_status = jarvis.agent_runtime.status()
    swarm_status = jarvis.swarm_runtime.status()
    agent_runs = jarvis.agent_runtime.list_runs(limit=20)
    swarm_runs = jarvis.swarm_runtime.list_runs(limit=20)
    history = list(jarvis.conversation_history[-100:])
    knowledge = await asyncio.to_thread(KNOWLEDGE.status)
    (branch, dirty_files), gpu_pct = await asyncio.gather(
        asyncio.to_thread(_git_state), asyncio.to_thread(_gpu_percent)
    )
    net_up, net_down = _network_rates()
    primary = str(preferences.get("primary_model") or PRIMARY_MODEL)
    model_rows = _model_inventory(jarvis, primary)
    selectable_models = [row for row in model_rows if row["selectable"]]
    control = request.app.state.control_service.snapshot()
    held = control.state.value != "running"
    state, detail, since = _agent_projection(agent_runs, held)
    active_agent_runs = sum(run.get("status") in ACTIVE_STATES for run in agent_runs)
    active_swarm_tasks = sum(
        task.get("status") in ACTIVE_STATES
        for run in swarm_runs for task in run.get("tasks", [])
    )
    completed_tasks = sum(
        task.get("status") == "completed"
        for run in swarm_runs for task in run.get("tasks", [])
    )
    total_tasks = sum(len(run.get("tasks", [])) for run in swarm_runs)
    started_at = str(history[0].get("timestamp", "")) if history else datetime.now().isoformat()
    try:
        started_epoch = datetime.fromisoformat(started_at).timestamp()
    except (TypeError, ValueError):
        started_epoch = time.time()

    graph = knowledge["graph"]
    vault = knowledge["vault"]
    provider_health = "healthy" if jarvis.get_status().get("nvidia_connected") else "down"
    project_rows = jarvis.workspace_registry.list()
    screens = {
        "AGENTS": {
            "title": "AGENT RUNTIME", "subtitle": "Durable local execution runs",
            "kpis": [
                {"k": "ACTIVE", "v": str(active_agent_runs), "tone": "info"},
                {"k": "DURABLE", "v": str(agent_status["durable_runs"]), "tone": "ok"},
                {"k": "WORKER", "v": "ONLINE" if agent_status["worker_online"] else "OFFLINE", "tone": "ok" if agent_status["worker_online"] else "danger"},
            ],
            "items": [{"name": r["goal"][:100], "sub": r["id"], "tag": r["status"], "tone": "danger" if r["status"] == "failed" else "info", "pct": 0, "meta": [["MODEL", r.get("model", "auto")], ["MODE", r.get("autonomy", "guarded")]]} for r in agent_runs[:12]],
        },
        "MISSIONS": {
            "title": "MISSION SWARMS", "subtitle": "Multi-agent orchestration",
            "kpis": [{"k": "ACTIVE", "v": str(swarm_status["active_swarms"]), "tone": "info"}, {"k": "TASKS", "v": f"{completed_tasks}/{total_tasks}", "tone": "ok"}, {"k": "CAP", "v": str(swarm_status["max_concurrent_agents"]), "tone": "muted"}],
            "items": [{"name": r["goal"][:100], "sub": r["id"], "tag": r["status"], "tone": "danger" if r["status"] == "failed" else "info", "pct": 0, "meta": [["MODE", r.get("mode", "")], ["PROJECT", r.get("project_id", "")]]} for r in swarm_runs[:12]],
        },
        "PROJECTS": {
            "title": "PROJECT WORKSPACES", "subtitle": "Registered execution boundaries",
            "kpis": [{"k": "PROJECTS", "v": str(len(project_rows)), "tone": "ok"}, {"k": "DIRTY", "v": str(dirty_files), "tone": "warn" if dirty_files else "ok"}],
            "items": [{"name": str(p.get("name", p.get("id", "project"))), "sub": str(p.get("root", "")), "tag": "PROTECTED" if p.get("protected") else "REGISTERED", "tone": "ok", "pct": 0, "meta": [["ID", str(p.get("id", ""))], ["ROOT", str(p.get("root", ""))[:80]]]} for p in project_rows[:20]],
        },
        "BRAIN": {
            "title": "KNOWLEDGE BRAIN", "subtitle": "Graphify and Obsidian evidence",
            "kpis": [{"k": "NODES", "v": str(graph["node_count"]), "tone": "info"}, {"k": "EDGES", "v": str(graph["edge_count"]), "tone": "info"}, {"k": "NOTES", "v": str(vault["markdown_count"]), "tone": "ok"}],
            "items": [{"name": "Graphify", "sub": str(graph["path"]), "tag": knowledge["health"].upper(), "tone": "ok" if knowledge["health"] == "good" else "warn", "pct": 0, "meta": [["COMMIT", str(graph.get("built_at_commit") or "unknown")], ["HYPEREDGES", str(graph["hyperedge_count"])]]}, {"name": "Obsidian Vault", "sub": str(vault["path"]), "tag": "ONLINE" if vault["exists"] else "MISSING", "tone": "ok" if vault["exists"] else "danger", "pct": 0, "meta": [["NOTES", str(vault["markdown_count"])], ["CONFIG", "YES" if vault["obsidian_configured"] else "NO"]]}],
        },
        "SECURITY": {
            "title": "CONTROL PLANE", "subtitle": "Authenticated, revision-aware runtime authority",
            "kpis": [{"k": "STATE", "v": control.state.value.upper(), "tone": "danger" if held else "ok"}, {"k": "REVISION", "v": str(control.revision), "tone": "info"}, {"k": "RESIDUE", "v": str(control.residue_count), "tone": "warn" if control.residue_count else "ok"}],
            "items": [{"name": "Global Control", "sub": control.reason_code, "tag": control.state.value.upper(), "tone": "danger" if held else "ok", "pct": 0, "meta": [["CONFIRMED", f"{control.confirmed_count}/{control.total_count}"], ["UPDATED", control.updated_at]]}],
        },
    }
    return {
        "at": datetime.now().astimezone().isoformat(), "source": "live",
        "agent": {"state": state, "detail": detail, "since": since, "autonomy": 2, "held": held},
        "telemetry": {
            "uptimeSec": max(0, int(time.time() - psutil.boot_time())),
            "cpuPct": psutil.cpu_percent(interval=None), "ramPct": memory.percent,
            "gpuPct": gpu_pct, "diskPct": disk.percent,
            "netUpMbs": net_up, "netDownMbs": net_down,
        },
        "session": {"id": f"session-{int(psutil.boot_time())}", "startedAt": started_at, "durationSec": max(0, int(time.time() - started_epoch)), "route": "AUTO" if preferences.get("auto_mode", True) else "PINNED", "messages": len(history)},
        "workspace": {"project": PROJECT_ROOT.name, "branch": branch, "dirtyFiles": dirty_files, "budgetMin": 0, "agentsActive": active_agent_runs + active_swarm_tasks, "agentsTotal": swarm_status["max_concurrent_agents"], "tasksComplete": completed_tasks, "tasksTotal": total_tasks, "missionWindow": "unbounded"},
        "flow": [
            {"name": "UI INTERFACE", "state": "ONLINE", "tone": "ok"},
            {"name": "AGENT CORE", "state": "ONLINE" if agent_status["worker_online"] else "DEGRADED", "tone": "ok" if agent_status["worker_online"] else "warn"},
            {"name": "VOICE SYSTEM", "state": "ARMED" if preferences.get("auto_mic", True) else "DISARMED", "tone": "info"},
            {"name": "API ROUTER", "state": f"{len(selectable_models)} READY / {len(model_rows)} KNOWN", "tone": "ok" if selectable_models else "warn"},
            {"name": "BRAIN GRAPH", "state": f"{graph['node_count']} NODES", "tone": "ok" if knowledge["health"] == "good" else "warn"},
        ],
        "graph": {"nodes": graph["node_count"], "edges": graph["edge_count"], "vaultNotes": vault["markdown_count"], "health": "healthy" if knowledge["health"] == "good" else "degraded"},
        "router": {"auto": bool(preferences.get("auto_mode", True)), "primary": primary, "models": model_rows},
        "providers": [{"id": "nvidia", "name": "NVIDIA NIM", "status": provider_health, "latencyMs": 0, "circuit": "closed" if provider_health != "down" else "open"}],
        "voice": {"armed": bool(preferences.get("auto_mic", True)), "inputDevice": "Browser selected input", "outputDevice": "System default", "profile": str(preferences.get("voice_profile", "en-GB")), "sensitivity": int(preferences.get("sensitivity", 6)), "level": 0},
        "events": _events(history, agent_runs), "screens": screens, "viz": {},
        "runtime": {"platform": platform.platform(), "controlRevision": control.revision},
    }


@router.get("/snapshot")
async def snapshot(request: Request, _principal: OperatorPrincipal = Depends(require_scope(OPERATOR_READ))):
    return await build_snapshot(request)


@router.get("/screen/{key}")
async def screen(key: str, request: Request, _principal: OperatorPrincipal = Depends(require_scope(OPERATOR_READ))):
    value = (await build_snapshot(request))["screens"].get(key.upper())
    if value is None:
        raise HTTPException(status_code=404, detail="Live data is not available for this screen")
    return value


@router.get("/viz/{key}")
async def visualization(key: str, request: Request, _principal: OperatorPrincipal = Depends(require_scope(OPERATOR_READ))):
    value = (await build_snapshot(request))["viz"].get(key.upper())
    if value is None:
        raise HTTPException(status_code=404, detail="Live visualization is not available")
    return value


@router.post("/command")
async def command(
    command: UICommand,
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(OPERATOR_EXECUTE)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    jarvis = _jarvis(request)
    payload = command.payload or {}
    if command.action == "submit_goal":
        goal = str(payload.get("goal", "")).strip()
        if not goal:
            raise HTTPException(status_code=422, detail="A goal is required")
        run = await jarvis.agent_runtime.submit(
            goal[:20_000], model=str(payload.get("model") or "auto"),
            autonomy="guarded", max_steps=min(12, max(1, int(payload.get("maxSteps", 8)))),
        )
        return {"ok": True, "message": f"Goal queued as {run.id}", "runId": run.id}
    if command.action == "set_auto_mode":
        enabled = bool(payload.get("enabled"))
        _write_preferences({"auto_mode": enabled})
        return {"ok": True, "message": f"Auto routing {'enabled' if enabled else 'disabled'}"}
    if command.action == "set_primary_model":
        model = str(payload.get("model", "")).strip()
        if not model or len(model) > 200:
            raise HTTPException(status_code=422, detail="A valid model id is required")
        selectable = {
            row["id"] for row in _model_inventory(jarvis, model)
            if row["selectable"]
        }
        if not selectable:
            raise HTTPException(status_code=409, detail="The live NVIDIA model catalog is not ready")
        if model not in selectable:
            raise HTTPException(status_code=409, detail="Model is not a live chat-compatible NVIDIA route")
        _write_preferences({"primary_model": model})
        return {"ok": True, "message": f"Primary route set to {model}"}
    if command.action == "set_voice_armed":
        armed = bool(payload.get("armed"))
        _write_preferences({"auto_mic": armed})
        return {"ok": True, "message": f"Voice channel {'armed' if armed else 'disarmed'}"}
    if command.action == "system_scan":
        data = await build_snapshot(request)
        telemetry = data["telemetry"]
        return {"ok": True, "message": f"System live: CPU {telemetry['cpuPct']:.0f}%, RAM {telemetry['ramPct']:.0f}%, disk {telemetry['diskPct']:.0f}%; control {data['agent']['state']}."}
    if command.action == "refresh_catalog":
        models = await jarvis._get_live_model_catalog(ttl_seconds=0)
        return {"ok": True, "message": f"NVIDIA catalog refreshed: {len(models)} compatible model ids cached."}
    raise HTTPException(status_code=422, detail="Unsupported dashboard command")


@stream_router.websocket("/ws/ui")
async def stream(websocket: WebSocket):
    await websocket.accept()
    cookie = websocket.scope.get("state", {}).get("operator_cookie")
    service: SessionService = websocket.app.state.session_service
    try:
        while True:
            service.recheck_transport(cookie, required_scope=OPERATOR_READ)
            await websocket.send_json({"type": "snapshot", "value": await build_snapshot(websocket)})
            await asyncio.sleep(2)
    except (AuthenticationError, AuthorizationError):
        await websocket.close(code=4403)
    except WebSocketDisconnect:
        pass


__all__ = ["router", "stream_router", "build_snapshot"]
