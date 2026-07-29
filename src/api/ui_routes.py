"""Canonical live-data contract for the Claude-designed JARVIS dashboard."""

from __future__ import annotations

import asyncio
import json
import math
import platform
import subprocess
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from src.api.dashboard_routes import DATA_DIR, KNOWLEDGE, PREFERENCES_FILE, _read_preferences
from src.core.control import (
    ControlAuthorizationError,
    ControlCommand,
    ControlError,
    InvalidControlTransitionError,
    StaleRevisionError,
)
from src.core.model_router import ModelRouter, PRIMARY_MODEL
from src.models.nvidia_models import ModelType, get_models_by_type
from src.security.auth import (
    APPROVALS_WRITE,
    EMERGENCY_STOP,
    OPERATOR_EXECUTE,
    OPERATOR_READ,
    RUNS_CONTROL,
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
SCREEN_KEYS = {
    "DASHBOARD", "CHAT", "VOICE", "MISSIONS", "AGENTS", "PROJECTS", "FILES",
    "NOTES", "BROWSER", "CODE", "BRAIN", "TASKS", "TOOLS", "AUTOMATIONS",
    "GIT", "SECURITY", "USAGE", "DEVICES", "SETTINGS",
}
_NET_SAMPLE: tuple[float, int, int] | None = None
_GRAPH_VIZ_CACHE: tuple[int, int, dict[str, Any] | None] | None = None


class UICommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_:-]+$")
    payload: dict[str, Any] | None = None


class UIApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=2_000)


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
    routed = {
        model_id
        for candidates in ModelRouter.TASK_MODELS.values()
        for model_id in candidates
    }
    model_ids = set(configured) | live | routed | {primary}
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


def _agent_projection(
    agent_runs: list[dict[str, Any]],
    held: bool,
    swarm_runs: list[dict[str, Any]] | None = None,
) -> tuple[str, str, str]:
    if held:
        return "paused", "Execution is held by the operator control plane.", datetime.now().isoformat()
    # A swarm's child agents deliberately carry internal role prompts.  Project the
    # operator-authored parent mission instead of exposing those implementation
    # prompts as JARVIS' current top-level activity.
    run = next(
        (
            candidate
            for candidate in (swarm_runs or [])
            if candidate.get("status") in ACTIVE_STATES | {"awaiting_confirmation"}
        ),
        None,
    )
    if run is not None:
        raw = str(run.get("status", "idle"))
        state = {
            "queued": "delegating", "planning": "thinking", "running": "delegating",
            "synthesizing": "thinking", "awaiting_confirmation": "awaiting_approval",
            "completed": "completed", "failed": "error", "cancelled": "paused",
        }.get(raw, "idle")
        detail = str(run.get("goal") or raw).replace("\n", " ")[:180]
        return state, detail, str(run.get("updated_at") or datetime.now().isoformat())
    run = next(
        (
            candidate
            for candidate in agent_runs
            if candidate.get("record_conversation", True) is not False
            if candidate.get("status") in ACTIVE_STATES | {"awaiting_confirmation"}
        ),
        None,
    )
    if run is None:
        return "idle", "Ready for Ahmed's directive.", datetime.now().isoformat()
    raw = str(run.get("status", "idle"))
    state = {
        "queued": "delegating", "planning": "thinking", "running": "executing",
        "synthesizing": "thinking", "awaiting_confirmation": "awaiting_approval",
        "completed": "completed", "failed": "error", "cancelled": "paused",
    }.get(raw, "idle")
    detail = str(run.get("goal") or raw).replace("\n", " ")[:180]
    return state, detail, str(run.get("updated_at") or datetime.now().isoformat())


def _events(
    history: list[dict[str, Any]],
    agent_runs: list[dict[str, Any]],
    swarm_runs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
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
    public_agent_runs = [
        run for run in agent_runs
        if run.get("record_conversation", True) is not False
    ]
    for run in public_agent_runs[:5]:
        events.append({
            "at": str(run.get("updated_at", "")), "who": "AGENT",
            "meta": f"{run.get('id', '')} · {run.get('status', '')}",
            "text": str(run.get("goal", ""))[:600],
            "level": "error" if run.get("status") == "failed" else "info",
        })
    for run in (swarm_runs or [])[:5]:
        events.append({
            "at": str(run.get("updated_at", "")), "who": "SWARM",
            "meta": f"{run.get('id', '')} · {run.get('status', '')}",
            "text": str(run.get("goal", ""))[:600],
            "level": "error" if run.get("status") == "failed" else "info",
        })
    return sorted(events, key=lambda item: item["at"])[-12:]


def _active_swarm_task_count(swarm_runs: list[dict[str, Any]]) -> int:
    """Count runnable child work only while its parent swarm is live."""

    return sum(
        task.get("status") in ACTIVE_STATES
        for run in swarm_runs
        if run.get("status") in ACTIVE_STATES
        for task in run.get("tasks", [])
    )


def _agent_card_action(run: dict[str, Any]) -> dict[str, Any] | None:
    """Return an explicit operator action for a durable agent card."""

    status = str(run.get("status", ""))
    run_id = str(run.get("id", ""))
    if not run_id:
        return None
    if status == "awaiting_confirmation":
        return {
            "command": "approve_agent_run",
            "payload": {"runId": run_id},
            "confirm": "Approve the currently pending guarded step for this agent run?",
        }
    if status in ACTIVE_STATES | {"awaiting_confirmation", "stopping"}:
        return {
            "command": "cancel_agent_run",
            "payload": {"runId": run_id},
            "confirm": "Cancel this active agent run?",
        }
    return None


def _swarm_card_action(run: dict[str, Any]) -> dict[str, Any] | None:
    """Return an explicit operator action for a durable swarm card."""

    status = str(run.get("status", ""))
    run_id = str(run.get("id", ""))
    if not run_id:
        return None
    if status == "awaiting_confirmation":
        return {
            "command": "approve_swarm_run",
            "payload": {"runId": run_id},
            "confirm": "Approve each currently pending guarded swarm step and resume the mission?",
        }
    if status in ACTIVE_STATES | {"stopping"}:
        return {
            "command": "cancel_swarm_run",
            "payload": {"runId": run_id},
            "confirm": "Cancel this active swarm mission?",
        }
    return None


async def _approve_agent_current_step(jarvis: Any, run_id: str) -> dict[str, Any]:
    run = jarvis.agent_runtime.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    if run.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail=f"Agent run is {run.status}, not awaiting confirmation")
    if not run.plan or run.current_step >= len(run.plan.steps):
        raise HTTPException(status_code=409, detail="Agent run has no pending step to approve")
    step = run.plan.steps[run.current_step]
    run = await jarvis.agent_runtime.approve(run_id, [step.id])
    return {
        "ok": True,
        "message": f"Approved guarded step {step.id}; agent is now {run.status}",
        "runId": run.id,
        "status": run.status,
    }


async def _approve_swarm_current_steps(jarvis: Any, run_id: str) -> dict[str, Any]:
    run = jarvis.swarm_runtime.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Swarm run not found")
    if run.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail=f"Swarm run is {run.status}, not awaiting confirmation")
    approved: list[str] = []
    for task in run.tasks.values():
        if task.status != "awaiting_confirmation" or not task.agent_run_id:
            continue
        agent_run = jarvis.agent_runtime.get_run(task.agent_run_id)
        if (
            agent_run is None or agent_run.status != "awaiting_confirmation"
            or not agent_run.plan or agent_run.current_step >= len(agent_run.plan.steps)
        ):
            continue
        step = agent_run.plan.steps[agent_run.current_step]
        await jarvis.agent_runtime.approve(agent_run.id, [step.id])
        approved.append(f"{agent_run.id}:{step.id}")
    if not approved:
        raise HTTPException(status_code=409, detail="Swarm has no current guarded step to approve")
    run = await jarvis.swarm_runtime.resume(run_id)
    return {
        "ok": True,
        "message": f"Approved {len(approved)} guarded swarm step(s); mission is now {run.status}",
        "runId": run.id,
        "status": run.status,
    }


def _require_dynamic_scope(principal: OperatorPrincipal, scope: str) -> None:
    if principal is None or scope not in principal.scopes:
        raise HTTPException(status_code=403, detail="scope_required")


async def _decide_run_approval(
    jarvis: Any,
    approval_id: str,
    decision: str,
) -> dict[str, Any]:
    """Resolve one approval id to exactly one guarded agent or swarm run."""

    approval_id = approval_id.strip()
    if not approval_id or len(approval_id) > 128:
        raise HTTPException(status_code=422, detail="A valid approval id is required")
    agent_run = jarvis.agent_runtime.get_run(approval_id)
    swarm_run = jarvis.swarm_runtime.get_run(approval_id)
    if agent_run is not None and swarm_run is not None:
        raise HTTPException(status_code=409, detail="Approval id is ambiguous")
    if agent_run is None and swarm_run is None:
        raise HTTPException(status_code=404, detail="Approval run not found")
    selected = agent_run if agent_run is not None else swarm_run
    if selected.status != "awaiting_confirmation":
        raise HTTPException(
            status_code=409,
            detail=f"Run is {selected.status}, not awaiting confirmation",
        )
    if decision == "approve":
        if agent_run is not None:
            return await _approve_agent_current_step(jarvis, approval_id)
        return await _approve_swarm_current_steps(jarvis, approval_id)
    if decision != "reject":
        raise HTTPException(status_code=422, detail="Decision must be approve or reject")
    try:
        cancelled = (
            jarvis.agent_runtime.cancel(approval_id)
            if agent_run is not None
            else jarvis.swarm_runtime.cancel(approval_id)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval run not found") from exc
    return {
        "ok": True,
        "message": f"Rejected guarded run {approval_id}; cancellation requested",
        "runId": cancelled.id,
        "status": cancelled.status,
    }


def _control_error(exc: ControlError) -> HTTPException:
    if isinstance(exc, StaleRevisionError):
        return HTTPException(status_code=409, detail="stale_revision")
    if isinstance(exc, ControlAuthorizationError):
        return HTTPException(status_code=403, detail=exc.code)
    if isinstance(exc, InvalidControlTransitionError):
        return HTTPException(status_code=409, detail="invalid_control_transition")
    return HTTPException(status_code=409, detail=exc.code)


def _transition_global_control(
    request: Request,
    principal: OperatorPrincipal,
    action: Literal["emergency_stop"],
) -> dict[str, Any]:
    _require_dynamic_scope(principal, EMERGENCY_STOP)
    service = request.app.state.control_service
    current = service.snapshot()
    state = current.state.value
    if state == "emergency_stopped":
        return {"ok": True, "message": "Emergency stop is already active", "controlState": state, "revision": current.revision}
    try:
        updated = service.transition(
            ControlCommand(
                action=action,
                scope_type="global",
                scope_id="global",
                expected_revision=current.revision,
                client_request_id=f"ui-{uuid.uuid4()}",
                reason_code="ui_command",
            ),
            actor_id=principal.actor_id,
            session_digest=principal.session_digest,
            scopes=frozenset(principal.scopes),
            reauthenticated=False,
        )
    except ControlError as exc:
        raise _control_error(exc) from None
    return {
        "ok": True,
        "message": "Emergency stop applied to all agent execution",
        "controlState": updated.state.value,
        "revision": updated.revision,
    }


def _controllable_run_ids(jarvis: Any) -> list[str]:
    terminal = {"completed", "failed", "cancelled", "stopped"}
    rows = [
        *jarvis.agent_runtime.list_runs(limit=200),
        *jarvis.swarm_runtime.list_runs(limit=200),
    ]
    return list(dict.fromkeys(
        str(row.get("id", ""))
        for row in rows
        if row.get("status") not in terminal and row.get("id")
    ))


def _transition_run_controls(
    request: Request,
    principal: OperatorPrincipal,
    jarvis: Any,
    action: Literal["pause", "reset"],
) -> dict[str, Any]:
    """Pause/release each live run without clearing global emergency authority."""

    _require_dynamic_scope(principal, RUNS_CONTROL)
    service = request.app.state.control_service
    global_state = service.snapshot().state.value
    if action == "reset" and global_state != "running":
        raise HTTPException(
            status_code=409,
            detail="Global control is held; use the protected control reset with fresh reauthentication",
        )
    changed: list[str] = []
    for run_id in _controllable_run_ids(jarvis):
        current = service.snapshot("run", run_id)
        if action == "pause" and current.state.value != "running":
            continue
        if action == "reset" and current.state.value != "paused":
            continue
        try:
            service.transition(
                ControlCommand(
                    action=action,
                    scope_type="run",
                    scope_id=run_id,
                    expected_revision=current.revision,
                    client_request_id=f"ui-{uuid.uuid4()}",
                    reason_code="ui_command",
                ),
                actor_id=principal.actor_id,
                session_digest=principal.session_digest,
                scopes=frozenset(principal.scopes),
                reauthenticated=False,
            )
        except ControlError as exc:
            raise _control_error(exc) from None
        changed.append(run_id)
    verb = "held" if action == "pause" else "released"
    return {
        "ok": True,
        "message": f"{len(changed)} active run(s) {verb}",
        "affectedRunIds": changed,
        "controlState": "paused" if action == "pause" and changed else "running",
    }


def _required_bool(payload: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        if key in payload:
            value = payload[key]
            if isinstance(value, bool):
                return value
            raise HTTPException(status_code=422, detail=f"{key} must be a boolean")
    raise HTTPException(status_code=422, detail=f"{keys[0]} is required")


def _autonomy_level(preferences: dict[str, Any]) -> int:
    try:
        level = int(preferences.get("autonomy_level", 2))
    except (TypeError, ValueError):
        return 2
    return level if level in {1, 2, 3, 4} else 2


def _graph_viz_from_payload(
    payload: dict[str, Any],
    *,
    max_nodes: int = 96,
    max_edges: int = 240,
) -> dict[str, Any] | None:
    """Project real Graphify nodes/links into a deterministic display layout."""

    raw_nodes = payload.get("nodes")
    raw_links = payload.get("links")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return None
    links = raw_links if isinstance(raw_links, list) else []
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").strip()
        if node_id and node_id not in nodes_by_id:
            nodes_by_id[node_id] = raw
    if not nodes_by_id:
        return None

    degree: Counter[str] = Counter()
    valid_links: list[tuple[str, str]] = []
    seen_links: set[tuple[str, str]] = set()
    for raw in links:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "").strip()
        target = str(raw.get("target") or "").strip()
        if source not in nodes_by_id or target not in nodes_by_id or source == target:
            continue
        key = tuple(sorted((source, target)))
        if key in seen_links:
            continue
        seen_links.add(key)
        valid_links.append((source, target))
        degree[source] += 1
        degree[target] += 1

    selected_ids = sorted(nodes_by_id, key=lambda node_id: (-degree[node_id], node_id))[
        :max(1, min(max_nodes, 256))
    ]
    selected = set(selected_ids)
    communities: dict[str, str] = {}
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for node_id in selected_ids:
        raw_community = nodes_by_id[node_id].get("community", 0)
        community = str(raw_community) if raw_community is not None else "0"
        communities[node_id] = community
        grouped[community].append(node_id)
    community_keys = sorted(grouped)
    community_index = {key: index for index, key in enumerate(community_keys)}
    max_degree = max((degree[node_id] for node_id in selected_ids), default=0)
    projected_nodes: list[dict[str, Any]] = []
    for node_id in selected_ids:
        group_key = communities[node_id]
        members = grouped[group_key]
        group_position = community_index[group_key]
        member_position = members.index(node_id)
        group_angle = 2 * math.pi * group_position / max(1, len(community_keys))
        center_radius = 0.0 if len(community_keys) == 1 else 0.52
        center_x = math.cos(group_angle) * center_radius
        center_y = math.sin(group_angle) * center_radius
        member_angle = 2 * math.pi * member_position / max(1, len(members))
        member_radius = 0.0 if len(members) == 1 else min(
            0.34, 0.08 + 0.035 * math.sqrt(member_position + 1)
        )
        x = max(-1.0, min(1.0, center_x + math.cos(member_angle) * member_radius))
        y = max(-1.0, min(1.0, center_y + math.sin(member_angle) * member_radius))
        z = 0.0 if len(members) == 1 else 0.45 * math.sin(member_angle * 1.7)
        raw = nodes_by_id[node_id]
        label = str(raw.get("label") or raw.get("norm_label") or node_id)
        projected_nodes.append({
            "id": node_id,
            "x": round(x, 6),
            "y": round(y, 6),
            "z": round(max(-1.0, min(1.0, z)), 6),
            "cluster": community_index[group_key],
            "size": round(0.6 + (1.4 * degree[node_id] / max_degree if max_degree else 0), 3),
            "label": label[:160],
        })

    index = {node_id: position for position, node_id in enumerate(selected_ids)}
    projected_edges = [
        [index[source], index[target]]
        for source, target in valid_links
        if source in selected and target in selected
    ][:max(0, min(max_edges, 1_000))]
    return {"kind": "graph", "nodes": projected_nodes, "edges": projected_edges}


def _brain_viz_projection() -> dict[str, Any] | None:
    global _GRAPH_VIZ_CACHE
    path = PROJECT_ROOT / ".planning" / "graphs" / "graph.json"
    try:
        stat = path.stat()
    except OSError:
        _GRAPH_VIZ_CACHE = None
        return None
    key = (stat.st_mtime_ns, stat.st_size)
    if _GRAPH_VIZ_CACHE and _GRAPH_VIZ_CACHE[:2] == key:
        return _GRAPH_VIZ_CACHE[2]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _GRAPH_VIZ_CACHE = (key[0], key[1], None)
        return None
    projection = _graph_viz_from_payload(payload) if isinstance(payload, dict) else None
    _GRAPH_VIZ_CACHE = (key[0], key[1], projection)
    return projection


def _agent_topology(
    agent_runs: list[dict[str, Any]],
    swarm_runs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    parent = next((run for run in swarm_runs if isinstance(run.get("agents"), list)), None)
    if parent is not None:
        spokes = []
        for row in parent.get("agents", [])[:24]:
            if not isinstance(row, dict):
                continue
            label = str(row.get("name") or row.get("role") or row.get("id") or "").strip()
            if not label:
                continue
            state = str(row.get("status") or "idle")
            spokes.append({
                "label": label[:80],
                "state": state,
                "ring": 1 if state in ACTIVE_STATES | {"awaiting_confirmation"} else 2,
            })
        if spokes:
            return {
                "kind": "topology",
                "hub": {"label": "JARVIS ORCHESTRATOR", "state": str(parent.get("status") or "idle")},
                "spokes": spokes,
            }
    public_runs = [
        run for run in agent_runs
        if run.get("record_conversation", True) is not False
        and run.get("status") not in {"completed", "failed", "cancelled"}
    ]
    if not public_runs:
        return None
    return {
        "kind": "topology",
        "hub": {"label": "JARVIS ORCHESTRATOR", "state": "active"},
        "spokes": [{
            "label": str(run.get("capability_profile") or run.get("id") or "AGENT")[:80].upper(),
            "state": str(run.get("status") or "idle"),
            "ring": 1,
        } for run in public_runs[:24]],
    }


def _mission_topology(swarm_runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = [run for run in swarm_runs if run.get("id")][:16]
    if not rows:
        return None
    active = any(run.get("status") in ACTIVE_STATES | {"awaiting_confirmation"} for run in rows)
    return {
        "kind": "topology",
        "hub": {"label": "MISSION CONTROL", "state": "active" if active else "idle"},
        "spokes": [{
            "label": str(run.get("goal") or run.get("id"))[:80],
            "state": str(run.get("status") or "unknown"),
            "ring": 1 if run.get("status") in ACTIVE_STATES | {"awaiting_confirmation"} else 2,
        } for run in rows],
    }


def _project_topology(project_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = [row for row in project_rows if row.get("id") or row.get("name")][:24]
    if not rows:
        return None
    return {
        "kind": "topology",
        "hub": {"label": "WORKSPACE REGISTRY", "state": "enforced"},
        "spokes": [{
            "label": str(row.get("name") or row.get("id"))[:80],
            "state": "sealed" if row.get("protected") else "granted",
            "ring": 2 if row.get("protected") else 1,
        } for row in rows],
    }


def _tool_topology(
    tool_rows: list[dict[str, Any]],
    *,
    security: bool = False,
) -> dict[str, Any] | None:
    rows = [row for row in tool_rows if row.get("name")][:32]
    if not rows:
        return None
    return {
        "kind": "topology",
        "hub": {
            "label": "TRUST POLICY" if security else "CAPABILITY POLICY",
            "state": "enforced",
        },
        "spokes": [{
            "label": str(row.get("name"))[:80].upper(),
            "state": "gated" if row.get("risk") == "write" else "granted",
            "ring": 2 if row.get("risk") == "write" else 1,
        } for row in rows],
    }


def _parse_event_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone()


def _hourly_series(
    timestamps: list[Any],
    *,
    unit: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    end = now or datetime.now().astimezone()
    if end.tzinfo is None:
        end = end.astimezone()
    end = end.replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=23)
    counts = [0] * 24
    observed = False
    for value in timestamps:
        parsed = _parse_event_time(value)
        if parsed is None:
            continue
        parsed = parsed.astimezone(end.tzinfo)
        offset = int((parsed.replace(minute=0, second=0, microsecond=0) - start).total_seconds() // 3600)
        if 0 <= offset < 24:
            counts[offset] += 1
            observed = True
    if not observed:
        return None
    points = [
        {"t": (start + timedelta(hours=index)).strftime("%H:00"), "v": value}
        for index, value in enumerate(counts)
    ]
    return {
        "kind": "series",
        "unit": unit,
        "points": points,
        "compare": None,
        "axis": [points[index]["t"] for index in (0, 6, 12, 18, 23)],
    }


def _tool_event_times(
    agent_runs: list[dict[str, Any]],
    tool_names: set[str],
) -> list[Any]:
    timestamps: list[Any] = []
    for run in agent_runs:
        for event in run.get("events", []):
            if not isinstance(event, dict) or event.get("stage") != "tool" or event.get("event_type") != "start":
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if data.get("tool") in tool_names:
                timestamps.append(event.get("timestamp"))
    return timestamps


async def build_snapshot(request: Request) -> dict[str, Any]:
    jarvis = _jarvis(request)
    preferences = _read_preferences()
    autonomy_level = _autonomy_level(preferences)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.cwd().anchor or str(PROJECT_ROOT.anchor))
    agent_status = jarvis.agent_runtime.status()
    swarm_status = jarvis.swarm_runtime.status()
    agent_runs = jarvis.agent_runtime.list_runs(limit=200)
    swarm_runs = jarvis.swarm_runtime.list_runs(limit=100)
    history = list(jarvis.conversation_history[-100:])
    knowledge = await asyncio.to_thread(KNOWLEDGE.status)
    (branch, dirty_files), gpu_pct = await asyncio.gather(
        asyncio.to_thread(_git_state), asyncio.to_thread(_gpu_percent)
    )
    net_up, net_down = _network_rates()
    primary = str(preferences.get("primary_model") or PRIMARY_MODEL)
    model_rows = _model_inventory(jarvis, primary)
    selectable_models = [row for row in model_rows if row["selectable"]]
    control_service = request.app.state.control_service
    control = control_service.snapshot()
    run_control_held = any(
        control_service.snapshot("run", run_id).state.value == "paused"
        for run_id in _controllable_run_ids(jarvis)
    )
    held = control.state.value != "running" or run_control_held
    state, detail, since = _agent_projection(agent_runs, held, swarm_runs)
    active_agent_runs = sum(run.get("status") in ACTIVE_STATES for run in agent_runs)
    active_swarm_tasks = _active_swarm_task_count(swarm_runs)
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
    brain_viz = await asyncio.to_thread(_brain_viz_projection)
    provider_connected = bool(jarvis.get_status().get("nvidia_connected"))
    provider_health = "healthy" if provider_connected and selectable_models else "degraded" if provider_connected else "down"
    project_rows = jarvis.workspace_registry.list()
    tool_rows = jarvis.agent_runtime.list_tools()
    schedule_rows = jarvis.agent_runtime.list_schedules()
    skill_rows = jarvis.get_available_skills()
    viz: dict[str, dict[str, Any]] = {}
    if brain_viz is not None:
        viz["BRAIN"] = brain_viz
    for key, value in (
        ("AGENTS", _agent_topology(agent_runs, swarm_runs)),
        ("MISSIONS", _mission_topology(swarm_runs)),
        ("PROJECTS", _project_topology(project_rows)),
        ("TOOLS", _tool_topology(tool_rows)),
        ("SECURITY", _tool_topology(tool_rows, security=True)),
        ("CHAT", _hourly_series(
            [item.get("timestamp") for item in history], unit="messages",
        )),
        ("USAGE", _hourly_series(
            [item.get("timestamp") for item in history if item.get("role") == "assistant"],
            unit="requests",
        )),
        ("FILES", _hourly_series(
            _tool_event_times(agent_runs, {
                "workspace_list", "workspace_read", "workspace_search", "workspace_write",
                "workspace_patch", "project_create", "directory_create",
            }),
            unit="operations",
        )),
        ("AUTOMATIONS", _hourly_series(
            [run.get("created_at") for run in agent_runs if run.get("schedule_id")],
            unit="triggers",
        )),
        ("GIT", _hourly_series(
            _tool_event_times(agent_runs, {"git_commit", "github_push"}),
            unit="operations",
        )),
    ):
        if value is not None:
            viz[key] = value
    workspace_entries: list[dict[str, Any]] = []
    try:
        for entry in sorted(PROJECT_ROOT.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))[:24]:
            workspace_entries.append({
                "name": entry.name,
                "path": str(entry.relative_to(PROJECT_ROOT)),
                "kind": "DIRECTORY" if entry.is_dir() else "FILE",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
    except OSError:
        workspace_entries = []
    screens = {
        "AGENTS": {
            "title": "AGENT RUNTIME", "subtitle": "Durable local execution runs",
            "kpis": [
                {"k": "ACTIVE", "v": str(active_agent_runs), "tone": "info"},
                {"k": "DURABLE", "v": str(agent_status["durable_runs"]), "tone": "ok"},
                {"k": "WORKER", "v": "ONLINE" if agent_status["worker_online"] else "OFFLINE", "tone": "ok" if agent_status["worker_online"] else "danger"},
            ],
            "items": [{
                "name": r["goal"][:100], "sub": r["id"], "tag": r["status"],
                "tone": "danger" if r["status"] == "failed" else "info", "pct": 0,
                "meta": [
                    ["MODEL", r.get("model", "auto")],
                    ["ACTION", "APPROVE" if r.get("status") == "awaiting_confirmation" else "CANCEL" if _agent_card_action(r) else "DETAIL"],
                ],
                "action": _agent_card_action(r),
            } for r in agent_runs[:12]],
        },
        "MISSIONS": {
            "title": "MISSION SWARMS", "subtitle": "Multi-agent orchestration",
            "kpis": [{"k": "ACTIVE", "v": str(swarm_status["active_swarms"]), "tone": "info"}, {"k": "TASKS", "v": f"{completed_tasks}/{total_tasks}", "tone": "ok"}, {"k": "CAP", "v": str(swarm_status["max_concurrent_agents"]), "tone": "muted"}],
            "items": [{
                "name": r["goal"][:100], "sub": r["id"], "tag": r["status"],
                "tone": "danger" if r["status"] == "failed" else "info", "pct": 0,
                "meta": [
                    ["MODE", r.get("mode", "")],
                    ["ACTION", "APPROVE" if r.get("status") == "awaiting_confirmation" else "CANCEL" if _swarm_card_action(r) else "DETAIL"],
                ],
                "action": _swarm_card_action(r),
            } for r in swarm_runs[:12]],
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
    screens.update({
        "CHAT": {
            "title": "CONVERSATION STREAM", "subtitle": "Live Jarvis conversation memory",
            "kpis": [
                {"k": "MESSAGES", "v": str(len(history)), "tone": "info"},
                {"k": "ROUTE", "v": primary, "tone": "ok"},
                {"k": "AUTO", "v": "ON" if preferences.get("auto_mode", True) else "OFF", "tone": "ok"},
            ],
            "items": [{
                "name": "AHMED" if str(item.get("role")) == "user" else "JARVIS",
                "sub": str(item.get("content", ""))[:240], "tag": str(item.get("role", "system")).upper(),
                "tone": "info" if str(item.get("role")) == "user" else "ok", "pct": 0,
                "meta": [["AT", str(item.get("timestamp", ""))[11:19]], ["SOURCE", "RUNTIME MEMORY"]],
            } for item in history[-16:]],
        },
        "FILES": {
            "title": "WORKSPACE FILES", "subtitle": str(PROJECT_ROOT),
            "kpis": [
                {"k": "VISIBLE", "v": str(len(workspace_entries)), "tone": "info"},
                {"k": "DIRTY", "v": str(dirty_files), "tone": "warn" if dirty_files else "ok"},
                {"k": "BOUNDARY", "v": "PROJECT", "tone": "ok"},
            ],
            "items": [{
                "name": entry["name"], "sub": entry["path"], "tag": entry["kind"],
                "tone": "info" if entry["kind"] == "DIRECTORY" else "muted", "pct": 0,
                "meta": [["SIZE", str(entry["size"]) if entry["size"] else "—"], ["SCOPE", "WORKSPACE"]],
            } for entry in workspace_entries],
        },
        "NOTES": {
            "title": "OBSIDIAN KNOWLEDGE VAULT", "subtitle": "Durable reviewed decisions and handoffs",
            "kpis": [
                {"k": "NOTES", "v": str(vault["markdown_count"]), "tone": "ok"},
                {"k": "CONFIG", "v": "READY" if vault["obsidian_configured"] else "MISSING", "tone": "ok" if vault["obsidian_configured"] else "warn"},
                {"k": "HEALTH", "v": knowledge["health"].upper(), "tone": "ok" if knowledge["health"] == "good" else "warn"},
            ],
            "items": [{
                "name": "JARVIS VAULT", "sub": str(vault["path"]),
                "tag": "ONLINE" if vault["exists"] else "MISSING", "tone": "ok" if vault["exists"] else "danger",
                "pct": 0, "meta": [["MARKDOWN", str(vault["markdown_count"])], ["CONFIG", "YES" if vault["obsidian_configured"] else "NO"]],
            }],
        },
        "BROWSER": {
            "title": "BROWSER CAPABILITIES", "subtitle": "Guarded web research and URL operations",
            "kpis": [
                {"k": "SEARCH", "v": "READY" if any(row["name"] == "web_search" for row in tool_rows) else "OFFLINE", "tone": "ok"},
                {"k": "OPEN URL", "v": "GATED" if any(row["name"] == "open_url" for row in tool_rows) else "OFFLINE", "tone": "warn"},
                {"k": "SESSIONS", "v": "ON DEMAND", "tone": "muted"},
            ],
            "items": [{
                "name": row["name"].upper(), "sub": row["description"], "tag": row["risk"].upper(),
                "tone": "warn" if row["risk"] == "write" else "ok", "pct": 0,
                "meta": [["BOUNDARY", "GUARDED"], ["STATUS", "AVAILABLE"]],
            } for row in tool_rows if row["name"] in {"web_search", "open_url", "github_repo_view"}],
        },
        "CODE": {
            "title": "CODE EXECUTION", "subtitle": "Workspace-bounded creation, patching, commands, and Git",
            "kpis": [
                {"k": "TOOLS", "v": str(sum(row["name"] in {"workspace_read", "workspace_search", "workspace_write", "workspace_patch", "command_run", "project_create"} for row in tool_rows)), "tone": "ok"},
                {"k": "RUNS", "v": str(len(agent_runs)), "tone": "info"},
                {"k": "WORKER", "v": "ONLINE" if agent_status["worker_online"] else "OFFLINE", "tone": "ok" if agent_status["worker_online"] else "danger"},
            ],
            "items": [{
                "name": row["name"].upper(), "sub": row["description"], "tag": row["risk"].upper(),
                "tone": "warn" if row["risk"] == "write" else "ok", "pct": 0,
                "meta": [["SCOPE", "WORKSPACE"], ["STATUS", "READY"]],
            } for row in tool_rows if row["name"] in {"workspace_read", "workspace_search", "workspace_write", "workspace_patch", "command_run", "project_create", "directory_create"}],
        },
        "TASKS": {
            "title": "DURABLE TASK QUEUE", "subtitle": "Persisted work survives restarts",
            "kpis": [
                {"k": "QUEUED", "v": str(sum(run.get("status") == "queued" for run in agent_runs)), "tone": "info"},
                {"k": "ACTIVE", "v": str(active_agent_runs + active_swarm_tasks), "tone": "warn" if active_agent_runs + active_swarm_tasks else "ok"},
                {"k": "COMPLETE", "v": str(sum(run.get("status") == "completed" for run in agent_runs)), "tone": "ok"},
            ],
            "items": [{
                "name": str(run.get("goal", ""))[:100], "sub": str(run.get("id", "")),
                "tag": str(run.get("status", "unknown")).upper(), "tone": "danger" if run.get("status") == "failed" else "info",
                "pct": 0, "meta": [
                    ["MODEL", str(run.get("model", "auto"))],
                    ["ACTION", "APPROVE" if run.get("status") == "awaiting_confirmation" else "CANCEL" if _agent_card_action(run) else "DETAIL"],
                ],
                "action": _agent_card_action(run),
            } for run in agent_runs[:20]],
        },
        "TOOLS": {
            "title": "GUARDED TOOL REGISTRY", "subtitle": "Real capabilities exposed to planner and agents",
            "kpis": [
                {"k": "TOTAL", "v": str(len(tool_rows)), "tone": "info"},
                {"k": "READ", "v": str(sum(row["risk"] == "read" for row in tool_rows)), "tone": "ok"},
                {"k": "WRITE", "v": str(sum(row["risk"] == "write" for row in tool_rows)), "tone": "warn"},
                {"k": "SKILLS", "v": str(len(skill_rows)), "tone": "info"},
            ],
            "items": [{
                "name": row["name"].upper(), "sub": row["description"], "tag": row["risk"].upper(),
                "tone": "warn" if row["risk"] == "write" else "ok", "pct": 0,
                "meta": [["POLICY", "CONFIRM" if row["risk"] == "write" else "ALLOW"], ["STATUS", "REGISTERED"]],
            } for row in tool_rows],
        },
        "AUTOMATIONS": {
            "title": "AUTOMATION SCHEDULES", "subtitle": "Durable scheduled agent goals",
            "kpis": [
                {"k": "TOTAL", "v": str(len(schedule_rows)), "tone": "info"},
                {"k": "ENABLED", "v": str(sum(bool(row.get("enabled", True)) for row in schedule_rows)), "tone": "ok"},
                {"k": "MIN INTERVAL", "v": "60 S", "tone": "muted"},
            ],
            "items": [{
                "name": str(row.get("goal", ""))[:100], "sub": str(row.get("id", "")),
                "tag": "ENABLED" if row.get("enabled", True) else "PAUSED", "tone": "ok" if row.get("enabled", True) else "warn",
                "pct": 0, "meta": [["NEXT", str(row.get("next_run_at", ""))], ["INTERVAL", str(row.get("interval_seconds") or "ONCE")]],
            } for row in schedule_rows],
        },
        "GIT": {
            "title": "GIT WORKSPACE", "subtitle": "Live repository state",
            "kpis": [
                {"k": "BRANCH", "v": branch.upper(), "tone": "info"},
                {"k": "CHANGED", "v": str(dirty_files), "tone": "warn" if dirty_files else "ok"},
                {"k": "ROOT", "v": PROJECT_ROOT.name.upper(), "tone": "ok"},
            ],
            "items": [{
                "name": branch, "sub": str(PROJECT_ROOT), "tag": "DIRTY" if dirty_files else "CLEAN",
                "tone": "warn" if dirty_files else "ok", "pct": 0,
                "meta": [["CHANGED", str(dirty_files)], ["BOUNDARY", "REGISTERED"]],
            }],
        },
        "USAGE": {
            "title": "PROVIDER ACCOUNTING", "subtitle": "Only measured values are reported",
            "kpis": [
                {"k": "REQUESTS", "v": str(sum(item.get("role") == "assistant" for item in history)), "tone": "info"},
                {"k": "TOKENS", "v": "NOT METERED", "tone": "muted"},
                {"k": "SPEND", "v": "NOT METERED", "tone": "muted"},
            ],
            "items": [{
                "name": "NVIDIA NIM", "sub": f"{len(selectable_models)} selectable / {len(model_rows)} known models",
                "tag": provider_health.upper(), "tone": "ok" if provider_health == "healthy" else "danger", "pct": 0,
                "meta": [["TOKENS", "UNAVAILABLE"], ["SPEND", "UNAVAILABLE"]],
            }],
        },
        "DEVICES": {
            "title": "DEVICE CHANNELS", "subtitle": "Browser-selected microphone and system output",
            "kpis": [
                {"k": "VOICE AUTHORITY", "v": "ENABLED" if preferences.get("auto_mic", True) else "DISABLED", "tone": "ok" if preferences.get("auto_mic", True) else "warn"},
                {"k": "HOST", "v": platform.node().upper(), "tone": "info"},
                {"k": "REMOTE", "v": "HTTPS", "tone": "ok"},
            ],
            "items": [
                {"name": "MICROPHONE", "sub": "Capture state is reported by the active browser after permission", "tag": "AUTHORITY ON" if preferences.get("auto_mic", True) else "DISABLED", "tone": "ok", "pct": 0, "meta": [["PROFILE", str(preferences.get("voice_profile", "en-GB"))], ["SENSITIVITY", str(preferences.get("sensitivity", 6))]]},
                {"name": "SPEAKER", "sub": "System default audio output", "tag": "READY", "tone": "ok", "pct": 0, "meta": [["VOICE", str(preferences.get("voice_profile", "en-GB"))], ["OUTPUT", "BROWSER"]]},
            ],
        },
        "SETTINGS": {
            "title": "RUNTIME SETTINGS", "subtitle": "Live non-secret operator preferences",
            "kpis": [
                {"k": "AUTO", "v": "ON" if preferences.get("auto_mode", True) else "OFF", "tone": "ok"},
                {"k": "PRIMARY", "v": primary, "tone": "info"},
                {"k": "VOICE", "v": str(preferences.get("voice_profile", "en-GB")), "tone": "info"},
                {"k": "AUTONOMY", "v": f"L{autonomy_level}", "tone": "warn" if autonomy_level == 4 else "info"},
            ],
            "items": [
                {"name": "AUTO ROUTING", "sub": "Health-aware model selection", "tag": "ON" if preferences.get("auto_mode", True) else "OFF", "tone": "ok", "pct": 0, "meta": [["PRIMARY", primary], ["CATALOG", str(len(selectable_models))]]},
                {"name": "VOICE AUTHORITY", "sub": "Microphone capture is browser-permission gated", "tag": "ENABLED" if preferences.get("auto_mic", True) else "DISABLED", "tone": "ok", "pct": 0, "meta": [["PROFILE", str(preferences.get("voice_profile", "en-GB"))], ["SENSITIVITY", str(preferences.get("sensitivity", 6))]]},
                {"name": "AUTONOMY LEVEL", "sub": "Capability policy and confirmation gates remain enforced at every level", "tag": f"L{autonomy_level}", "tone": "warn" if autonomy_level == 4 else "info", "pct": 0, "meta": [["L4", "FULL WORKSPACE"], ["GUARDS", "ENFORCED"]]},
            ],
        },
    })
    return {
        "at": datetime.now().astimezone().isoformat(), "source": "live",
        "agent": {"state": state, "detail": detail, "since": since, "autonomy": autonomy_level, "held": held},
        "telemetry": {
            "uptimeSec": max(0, int(time.time() - psutil.boot_time())),
            "cpuPct": psutil.cpu_percent(interval=None), "ramPct": memory.percent,
            "gpuPct": gpu_pct, "diskPct": disk.percent,
            "netUpMbs": net_up, "netDownMbs": net_down,
        },
        "session": {"id": f"session-{int(psutil.boot_time())}", "startedAt": started_at, "durationSec": max(0, int(time.time() - started_epoch)), "route": "AUTO" if preferences.get("auto_mode", True) else "PINNED", "messages": len(history)},
        "workspace": {
            "project": PROJECT_ROOT.name, "branch": branch, "dirtyFiles": dirty_files,
            "budgetMin": 0, "agentsActive": active_agent_runs + active_swarm_tasks,
            "agentsTotal": swarm_status["max_concurrent_agents"],
            "tasksComplete": completed_tasks, "tasksTotal": total_tasks,
            "missionWindow": "unbounded",
            "projects": [
                {"id": str(row.get("id", "")), "name": str(row.get("name", row.get("id", "project"))), "protected": bool(row.get("protected"))}
                for row in project_rows
            ],
        },
        "flow": [
            {"name": "UI INTERFACE", "state": "ONLINE", "tone": "ok"},
            {"name": "AGENT CORE", "state": "ONLINE" if agent_status["worker_online"] else "DEGRADED", "tone": "ok" if agent_status["worker_online"] else "warn"},
            {"name": "VOICE SYSTEM", "state": "BROWSER AUTHORITY ON" if preferences.get("auto_mic", True) else "DISABLED", "tone": "info"},
            {"name": "API ROUTER", "state": f"{len(selectable_models)} READY / {len(model_rows)} KNOWN", "tone": "ok" if selectable_models else "warn"},
            {"name": "BRAIN GRAPH", "state": f"{graph['node_count']} NODES", "tone": "ok" if knowledge["health"] == "good" else "warn"},
        ],
        "graph": {"nodes": graph["node_count"], "edges": graph["edge_count"], "vaultNotes": vault["markdown_count"], "health": "healthy" if knowledge["health"] == "good" else "degraded"},
        "router": {"auto": bool(preferences.get("auto_mode", True)), "primary": primary, "models": model_rows},
        "providers": [{"id": "nvidia", "name": "NVIDIA NIM", "status": provider_health, "latencyMs": 0, "circuit": "closed" if provider_health != "down" else "open"}],
        "voice": {"armed": bool(preferences.get("auto_mic", True)), "inputDevice": "Browser selected input", "outputDevice": "System default", "profile": str(preferences.get("voice_profile", "en-GB")), "sensitivity": int(preferences.get("sensitivity", 6)), "level": 0},
        "usage": {"requests": sum(item.get("role") == "assistant" for item in history), "tokens": 0, "spendUsd": 0, "capUsd": 0, "metered": False, "series": []},
        "events": _events(history, agent_runs, swarm_runs), "screens": screens, "viz": viz,
        "runtime": {
            "platform": platform.platform(),
            "controlRevision": control.revision,
            "visualizationKeys": sorted(viz),
        },
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


@router.post("/approval/{approval_id}")
async def decide_approval(
    approval_id: str,
    decision: UIApprovalDecision,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(APPROVALS_WRITE)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    """Approve or reject exactly one currently guarded agent/swarm run."""
    if decision.decision == "reject":
        _require_dynamic_scope(principal, RUNS_CONTROL)
    return await _decide_run_approval(
        _jarvis(request), approval_id, decision.decision,
    )


@router.post("/agent/runs/{run_id}/approve-current")
async def approve_agent_current_step(
    run_id: str,
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(APPROVALS_WRITE)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    """Approve exactly the currently pending agent step under the approval scope."""
    return await _approve_agent_current_step(_jarvis(request), run_id)


@router.post("/agent/runs/{run_id}/cancel")
async def cancel_agent_run(
    run_id: str,
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(RUNS_CONTROL)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    """Cancel one agent run under the dedicated run-control scope."""
    try:
        run = _jarvis(request).agent_runtime.cancel(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc
    return {
        "ok": True, "message": f"Agent cancellation requested; status {run.status}",
        "runId": run.id, "status": run.status,
    }


@router.post("/swarm/runs/{run_id}/approve-current")
async def approve_swarm_current_steps(
    run_id: str,
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(APPROVALS_WRITE)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    """Approve one current guarded step per waiting child, then resume the swarm."""
    return await _approve_swarm_current_steps(_jarvis(request), run_id)


@router.post("/swarm/runs/{run_id}/cancel")
async def cancel_swarm_run(
    run_id: str,
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(RUNS_CONTROL)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    """Cancel one swarm mission under the dedicated run-control scope."""
    try:
        run = _jarvis(request).swarm_runtime.cancel(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Swarm run not found") from exc
    return {
        "ok": True, "message": f"Swarm cancellation requested; status {run.status}",
        "runId": run.id, "status": run.status,
    }


@router.post("/command")
async def command(
    command: UICommand,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(OPERATOR_EXECUTE)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    jarvis = _jarvis(request)
    payload = command.payload or {}
    if command.action == "submit_goal":
        goal = str(payload.get("goal", "")).strip()
        if not goal:
            raise HTTPException(status_code=422, detail="A goal is required")
        project_id = str(payload.get("projectId") or "jarvis").strip()
        if not project_id or len(project_id) > 80:
            raise HTTPException(status_code=422, detail="A valid project id is required")
        try:
            workspace_root = jarvis.workspace_registry.resolve(project_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Project workspace is not registered") from exc
        default_autonomy = "full" if _autonomy_level(_read_preferences()) == 4 else "guarded"
        autonomy = str(payload.get("autonomy") or default_autonomy).strip().lower()
        if autonomy not in {"guarded", "full"}:
            raise HTTPException(status_code=422, detail="Autonomy must be guarded or full")
        model = str(payload.get("model") or "auto").strip()
        if not model or len(model) > 200:
            raise HTTPException(status_code=422, detail="A valid model id is required")
        try:
            max_agents = min(8, max(1, int(payload.get("maxAgents", 8))))
            max_runtime_seconds = min(86_400, max(60, int(payload.get("maxRuntimeSeconds", 3_600))))
            max_steps = min(12, max(1, int(payload.get("maxSteps", 8))))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Execution limits must be integers") from exc
        dispatch = str(payload.get("dispatch") or "agent").strip().lower()
        if dispatch in {"swarm", "council", "cowork"}:
            run = await jarvis.swarm_runtime.submit(
                goal[:20_000], mode=dispatch, project_id=project_id,
                autonomy=autonomy, model=model,
                max_agents=max_agents, max_runtime_seconds=max_runtime_seconds,
            )
            return {
                "ok": True,
                "message": f"{dispatch.title()} queued as {run.id}",
                "runId": run.id,
            }
        if dispatch != "agent":
            raise HTTPException(status_code=422, detail="Dispatch mode must be agent, swarm, council, or cowork")
        run = await jarvis.agent_runtime.submit(
            goal[:20_000], model=model, autonomy=autonomy,
            max_steps=max_steps, workspace_root=workspace_root,
        )
        return {"ok": True, "message": f"Goal queued as {run.id}", "runId": run.id}
    if command.action in {
        "approve_agent_run", "cancel_agent_run", "approve_swarm_run", "cancel_swarm_run",
    }:
        raise HTTPException(
            status_code=403,
            detail="Use the dedicated approval or run-control endpoint for this action",
        )
    if command.action in {"approve", "reject"}:
        approval_id = str(payload.get("id") or "").strip()
        required_scope = APPROVALS_WRITE if command.action == "approve" else RUNS_CONTROL
        _require_dynamic_scope(principal, required_scope)
        return await _decide_run_approval(jarvis, approval_id, command.action)
    if command.action == "emergency_stop":
        return _transition_global_control(request, principal, "emergency_stop")
    if command.action == "hold":
        return _transition_run_controls(request, principal, jarvis, "pause")
    if command.action == "release":
        return _transition_run_controls(request, principal, jarvis, "reset")
    if command.action in {"set_auto_mode", "set_auto_route"}:
        enabled = _required_bool(payload, "enabled", "auto")
        _write_preferences({"auto_mode": enabled})
        return {"ok": True, "message": f"Auto routing {'enabled' if enabled else 'disabled'}"}
    if command.action in {"set_primary_model", "set_route"}:
        model = str(payload.get("model") or payload.get("modelId") or "").strip()
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
    if command.action in {"set_autonomy", "set_autonomy_level"}:
        level = payload.get("level")
        if isinstance(level, bool) or not isinstance(level, int) or level not in {1, 2, 3, 4}:
            raise HTTPException(status_code=422, detail="Autonomy level must be an integer from 1 to 4")
        _write_preferences({"autonomy_level": level})
        return {
            "ok": True,
            "message": (
                f"Autonomy preference set to L{level}; capability policy, workspace boundaries, "
                "secret protection, external-action controls, and destructive confirmations remain enforced"
            ),
            "level": level,
        }
    if command.action in {"set_voice_armed", "voice_arm", "voice_disarm"}:
        armed = (
            True if command.action == "voice_arm"
            else False if command.action == "voice_disarm"
            else _required_bool(payload, "armed")
        )
        _write_preferences({"auto_mic": armed})
        return {"ok": True, "message": f"Voice channel {'armed' if armed else 'disarmed'}"}
    if command.action == "push_to_talk":
        try:
            capture_ms = int(payload.get("ms", 6_000))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Push-to-talk duration must be an integer") from exc
        if not 250 <= capture_ms <= 30_000:
            raise HTTPException(status_code=422, detail="Push-to-talk duration must be 250-30000 ms")
        return {
            "ok": True,
            "message": f"Browser push-to-talk capture authorized for {capture_ms} ms",
            "captureMs": capture_ms,
            "transcribePath": "/api/voice/transcribe",
        }
    if command.action == "send_message":
        text = str(payload.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="Message text is required")
        if len(text) > 20_000:
            raise HTTPException(status_code=422, detail="Message text exceeds 20000 characters")
        project_id = str(payload.get("projectId") or "jarvis").strip()
        try:
            workspace_root = jarvis.workspace_registry.resolve(project_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Project workspace is not registered") from exc
        preferences = _read_preferences()
        autonomy = "full" if _autonomy_level(preferences) == 4 else "guarded"
        model = (
            "auto" if preferences.get("auto_mode", True)
            else str(preferences.get("primary_model") or PRIMARY_MODEL)
        )
        run = await jarvis.agent_runtime.submit(
            text,
            model=model,
            autonomy=autonomy,
            max_steps=8,
            workspace_root=workspace_root,
        )
        return {
            "ok": True,
            "message": f"Goal queued for durable execution as {run.id}",
            "runId": run.id,
        }
    if command.action == "open_screen":
        key = str(payload.get("key") or "").strip().upper()
        if key not in SCREEN_KEYS:
            raise HTTPException(status_code=422, detail="Unknown dashboard screen")
        control_service = request.app.state.control_service
        audit_id = control_service.record_runtime_event(
            action="ui_open_screen",
            outcome="observed",
            boundary="ui_navigation",
            snapshot=control_service.snapshot(),
            code=key,
            applied=True,
        )
        return {
            "ok": True,
            "message": f"Opened {key}",
            "screen": key,
            "auditId": audit_id,
        }
    if command.action == "quick_command":
        name = " ".join(str(payload.get("name") or "").strip().upper().split())
        if name in {"SYSTEM SCAN", "STATUS REPORT"}:
            data = await build_snapshot(request)
            telemetry = data["telemetry"]
            return {
                "ok": True,
                "message": (
                    f"System live: CPU {telemetry['cpuPct']:.0f}%, RAM {telemetry['ramPct']:.0f}%, "
                    f"disk {telemetry['diskPct']:.0f}%; control {data['agent']['state']}."
                ),
            }
        if name == "PROVIDER SWEEP":
            models = await jarvis._get_live_model_catalog(ttl_seconds=0)
            return {"ok": True, "message": f"Provider sweep complete: {len(models)} compatible model ids cached."}
        if name in {"HOLD ALL AGENTS", "LOCK WORKSPACE"}:
            return _transition_run_controls(request, principal, jarvis, "pause")
        if name == "RESUME MISSIONS":
            return _transition_run_controls(request, principal, jarvis, "reset")
        if name == "MORNING BRIEF":
            response = await jarvis.chat(
                "Give Ahmed a concise live morning brief using current system and project context.",
                stream=False,
            )
            return {"ok": True, "message": str(response), "response": str(response)}
        screen_for_command = {
            "BROWSER OPEN": "BROWSER",
            "NOTE CAPTURE": "NOTES",
            "FILE SEARCH": "FILES",
            "CODE EXECUTOR": "CODE",
        }.get(name)
        if screen_for_command:
            return {
                "ok": True,
                "message": f"Opened {screen_for_command}; provide the target before execution",
                "screen": screen_for_command,
            }
        if name == "VOICE TEST":
            return {
                "ok": True,
                "message": "Voice test ready in the browser audio channel",
                "voiceTest": True,
                "text": "Good day, Ahmed. JARVIS voice systems are online.",
            }
        raise HTTPException(status_code=422, detail="Unknown quick command")
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
