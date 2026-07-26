"""Functional dashboard API routes backed by local JARVIS services."""

from __future__ import annotations

import json
import os
import platform
import asyncio
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import psutil
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.config import config
from src.core.knowledge_vault import KnowledgeVault
from src.skills.nvidia_catalog import NvidiaSkillsCatalog


router = APIRouter(prefix="/api", tags=["dashboard"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PREFERENCES_FILE = DATA_DIR / "dashboard_preferences.json"
NOTES_FILE = DATA_DIR / "notes.jsonl"
TASKS_FILE = DATA_DIR / "tasks.json"
NVIDIA_SKILLS = NvidiaSkillsCatalog()
KNOWLEDGE = KnowledgeVault(PROJECT_ROOT)


def _jarvis(request: Request):
    instance = getattr(request.app.state, "jarvis", None)
    if instance is None:
        raise HTTPException(status_code=503, detail="JARVIS is not initialized")
    return instance


def _disk_usage() -> dict[str, Any]:
    root = Path.cwd().anchor or str(PROJECT_ROOT.anchor)
    usage = psutil.disk_usage(root)
    return {
        "path": root,
        "percent": usage.percent,
        "used": usage.used,
        "total": usage.total,
        "free": usage.free,
    }


@router.get("/dashboard/state")
async def dashboard_state(request: Request):
    """Return live machine and JARVIS state for the dashboard HUD."""
    jarvis = _jarvis(request)
    memory = psutil.virtual_memory()
    net = psutil.net_io_counters()
    boot_time = psutil.boot_time()
    return {
        "system": {
            "os": platform.platform(),
            "hostname": platform.node(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "cpu_count": psutil.cpu_count(),
            "memory_percent": memory.percent,
            "memory_used": memory.used,
            "memory_total": memory.total,
            "disk": _disk_usage(),
            "network": {"bytes_sent": net.bytes_sent, "bytes_received": net.bytes_recv},
            "uptime_seconds": max(0, int(time.time() - boot_time)),
        },
        "jarvis": jarvis.get_status(),
        "preferences": _read_preferences(),
    }


@router.get("/session")
async def session(request: Request):
    jarvis = _jarvis(request)
    history = list(jarvis.conversation_history[-100:])
    return {
        "id": f"session-{int(psutil.boot_time())}",
        "started": history[0].get("timestamp") if history else None,
        "messages": history,
        "message_count": len(history),
    }


@router.delete("/session")
async def clear_session(request: Request):
    jarvis = _jarvis(request)
    jarvis.conversation_history.clear()
    return {"cleared": True}


@router.get("/brain")
async def brain(request: Request):
    jarvis = _jarvis(request)
    skills = jarvis.get_available_skills()
    knowledge = KNOWLEDGE.status()
    nodes = [
        {"id": "jarvis", "label": "JARVIS", "kind": "core"},
        {"id": "graphify", "label": "Graphify Code Graph", "kind": "knowledge"},
        {"id": "obsidian", "label": "Obsidian Vault", "kind": "knowledge"},
        {"id": "memory", "label": "Vector Memory", "kind": "memory"},
        {"id": "router", "label": "Model Router", "kind": "router"},
    ]
    nodes.extend(
        {"id": f"skill:{name}", "label": name.replace("_", " ").title(), "kind": "skill"}
        for name in skills
    )
    edges = [{"source": "jarvis", "target": node["id"]} for node in nodes[1:]]
    return {
        "nodes": nodes,
        "edges": edges,
        "health": knowledge["health"] if skills else "degraded",
        **knowledge,
    }


class BrainSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=20, ge=1, le=100)


class BrainOpenRequest(BaseModel):
    target: str = Field(default="vault", pattern="^(vault|graph|report)$")
    confirm: bool = False


@router.post("/brain/search")
async def search_brain(payload: BrainSearchRequest):
    results = KNOWLEDGE.search(payload.query, payload.limit)
    return {"query": payload.query, "results": results, "count": len(results)}


@router.post("/brain/open")
async def open_brain(payload: BrainOpenRequest):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required")
    status = KNOWLEDGE.status()
    targets = {
        "vault": Path(status["vault"]["path"]),
        "graph": Path(status["graph"]["html_path"]),
        "report": Path(status["graph"]["report_path"]),
    }
    path = targets[payload.target]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Brain {payload.target} is unavailable")
    if os.name == "nt":
        target = (
            f"obsidian://open?path={quote(str(path), safe='')}"
            if payload.target == "vault"
            else str(path)
        )
        await asyncio.to_thread(os.startfile, target)
    else:
        process = await asyncio.create_subprocess_exec("xdg-open", str(path))
        await process.wait()
    return {"opened": True, "target": payload.target, "path": str(path)}


@router.get("/keys/status")
async def key_status():
    key = config.get("nvidia.api_key") or os.getenv("NVIDIA_API_KEY")
    return {
        "provider": "nvidia",
        "configured": bool(key),
        "masked": f"{key[:5]}…{key[-4:]}" if key and len(key) >= 10 else None,
    }


@router.get("/nvidia-skills")
async def nvidia_skills(
    query: str | None = None,
    category: str | None = None,
    product: str | None = None,
    limit: int = 50,
):
    safe_limit = max(1, min(limit, 230))
    if query:
        skills = NVIDIA_SKILLS.search(query, limit=safe_limit)
    else:
        skills = NVIDIA_SKILLS.list_skills(category=category, product=product)[:safe_limit]
    return {
        "skills": [skill.to_dict() for skill in skills],
        "count": len(skills),
        "status": NVIDIA_SKILLS.status(),
    }


class NvidiaSkillRecommendationRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4_000)
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/nvidia-skills/recommend")
async def recommend_nvidia_skills(payload: NvidiaSkillRecommendationRequest):
    matches = NVIDIA_SKILLS.recommend(payload.task, limit=payload.limit)
    return {
        "task": payload.task,
        "recommendations": [skill.to_dict() for skill in matches],
        "executes_remote_code": False,
    }


@router.post("/nvidia-skills/refresh")
async def refresh_nvidia_skills():
    skills = NVIDIA_SKILLS.refresh()
    return {"count": len(skills), "status": NVIDIA_SKILLS.status()}


class FileSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=30, ge=1, le=100)


@router.post("/files/search")
async def search_files(payload: FileSearchRequest):
    query = payload.query.casefold()
    results: list[dict[str, Any]] = []
    excluded = {".git", "node_modules", "dist", "__pycache__", ".venv", "venv"}
    for path in PROJECT_ROOT.rglob("*"):
        if any(part in excluded for part in path.parts) or not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if query not in str(relative).casefold():
            continue
        stat = path.stat()
        results.append({"name": path.name, "path": str(relative), "size": stat.st_size})
        if len(results) >= payload.limit:
            break
    return {"query": payload.query, "results": results, "count": len(results)}


class FilePathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1_000)
    confirm: bool = False


def _safe_project_path(relative_path: str) -> Path:
    candidate = (PROJECT_ROOT / relative_path).resolve()
    root = PROJECT_ROOT.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Path must stay inside the JARVIS workspace")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File was not found")
    return candidate


@router.post("/files/read")
async def read_file(payload: FilePathRequest):
    path = _safe_project_path(payload.path)
    if path.stat().st_size > 500_000:
        raise HTTPException(status_code=413, detail="Preview is limited to 500 KB")
    raw = path.read_bytes()
    if b"\x00" in raw[:4096]:
        return {"path": payload.path, "binary": True, "size": len(raw), "content": "Binary file — preview unavailable"}
    return {"path": payload.path, "binary": False, "size": len(raw), "content": raw.decode("utf-8", errors="replace")}


@router.post("/files/open")
async def open_file(payload: FilePathRequest):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required")
    path = _safe_project_path(payload.path)
    if os.name == "nt":
        await asyncio.to_thread(os.startfile, str(path))
    else:
        process = await asyncio.create_subprocess_exec("xdg-open", str(path))
        await process.wait()
    return {"opened": True, "path": payload.path}


class NoteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


@router.post("/notes")
async def create_note(payload: NoteRequest):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    note = {"id": f"note-{time.time_ns()}", "content": payload.content, "created_at": time.time()}
    with NOTES_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(note, ensure_ascii=False) + "\n")
    return note


@router.get("/notes")
async def list_notes(limit: int = 50):
    if not NOTES_FILE.exists():
        return {"notes": []}
    lines = NOTES_FILE.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 200)) :]
    return {"notes": [json.loads(line) for line in reversed(lines) if line.strip()]}


@router.delete("/notes/{note_id}")
async def delete_note(note_id: str):
    if not NOTES_FILE.exists():
        raise HTTPException(status_code=404, detail="Note was not found")
    notes = [json.loads(line) for line in NOTES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    remaining = [note for note in notes if note.get("id") != note_id]
    if len(remaining) == len(notes):
        raise HTTPException(status_code=404, detail="Note was not found")
    NOTES_FILE.write_text("".join(json.dumps(note, ensure_ascii=False) + "\n" for note in remaining), encoding="utf-8")
    return {"deleted": True, "id": note_id}


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")
    completed: bool | None = None


def _read_tasks() -> list[dict[str, Any]]:
    if not TASKS_FILE.exists():
        return []
    try:
        value = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_tasks(tasks: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")


@router.get("/tasks")
async def list_tasks():
    tasks = _read_tasks()
    return {"tasks": tasks, "count": len(tasks)}


@router.post("/tasks")
async def create_task(payload: TaskCreateRequest):
    tasks = _read_tasks()
    task = {"id": f"task-{time.time_ns()}", "title": payload.title, "priority": payload.priority, "completed": False, "created_at": time.time()}
    tasks.insert(0, task)
    _write_tasks(tasks)
    return task


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, payload: TaskUpdateRequest):
    tasks = _read_tasks()
    for task in tasks:
        if task.get("id") == task_id:
            task.update(payload.model_dump(exclude_none=True))
            task["updated_at"] = time.time()
            _write_tasks(tasks)
            return task
    raise HTTPException(status_code=404, detail="Task was not found")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    tasks = _read_tasks()
    remaining = [task for task in tasks if task.get("id") != task_id]
    if len(remaining) == len(tasks):
        raise HTTPException(status_code=404, detail="Task was not found")
    _write_tasks(remaining)
    return {"deleted": True, "id": task_id}


class BrowserOpenRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


@router.post("/browser/open")
async def validate_browser_url(payload: BrowserOpenRequest):
    parsed = urlparse(payload.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Only valid HTTP(S) URLs can be opened")
    return {"url": payload.url, "allowed": True}


class CodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20_000)
    language: str = "python"
    confirm: bool = False


@router.post("/code/execute")
async def execute_code(payload: CodeRequest):
    """Execute user-confirmed Python in isolated mode with a short timeout."""
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required")
    if payload.language.casefold() != "python":
        raise HTTPException(status_code=400, detail="Only Python execution is currently supported")
    with tempfile.TemporaryDirectory(prefix="jarvis-code-") as workdir:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            payload.code,
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise HTTPException(status_code=408, detail="Code execution timed out") from exc
    return {
        "stdout": stdout.decode(errors="replace")[-20_000:],
        "stderr": stderr.decode(errors="replace")[-20_000:],
        "exit_code": process.returncode,
    }


class PreferencesRequest(BaseModel):
    auto_mic: bool | None = None
    clear_wake: bool | None = None
    owner_voice_only: bool | None = None
    sensitivity: int | None = Field(default=None, ge=0, le=10)
    auto_mode: bool | None = None
    ui_preference: str | None = Field(default=None, max_length=100)


def _read_preferences() -> dict[str, Any]:
    defaults = {
        "auto_mic": True,
        "clear_wake": True,
        "owner_voice_only": True,
        "sensitivity": 6,
        "auto_mode": True,
    }
    if not PREFERENCES_FILE.exists():
        return defaults
    try:
        return {**defaults, **json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return defaults


@router.put("/dashboard/preferences")
async def save_preferences(payload: PreferencesRequest):
    preferences = _read_preferences()
    preferences.update(payload.model_dump(exclude_none=True))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PREFERENCES_FILE.write_text(json.dumps(preferences, indent=2), encoding="utf-8")
    return preferences
