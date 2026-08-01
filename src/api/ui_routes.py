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
from urllib.parse import urlsplit

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.approval_receipts import (
    APPROVAL_CONFLICT_DETAIL,
    SWARM_APPROVAL_APPLIED_CODE,
    SWARM_APPROVAL_PARTIAL_CODE,
    SWARM_RESUME_CONFLICT_DETAIL,
    approval_applied_item,
    swarm_approval_receipt,
)
from src.api.dashboard_routes import DATA_DIR, KNOWLEDGE, PREFERENCES_FILE, _read_preferences
from src.config import config
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
CAPABILITY_STATES = frozenset({
    "available", "configured", "verified", "degraded", "unavailable",
})
CAPABILITY_TONES = {
    "verified": "ok",
    "available": "info",
    "configured": "muted",
    "degraded": "warn",
    "unavailable": "danger",
}
MOBILE_ACCESS_FILE = DATA_DIR / "mobile-access.json"
MOBILE_ACCESS_TTL_SECONDS = 300
MODEL_CATALOG_TTL_SECONDS = 300.0
class UICommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_:-]+$")
    payload: dict[str, Any] | None = None


class UIAgentApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=40)
    challenge_id: str = Field(min_length=16, max_length=128)


class UISwarmApprovalReference(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agent_run_id: str = Field(alias="agentRunId", min_length=1, max_length=128)
    step_id: str = Field(alias="stepId", min_length=1, max_length=40)
    challenge_id: str = Field(alias="challengeId", min_length=16, max_length=128)


class UISwarmApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approvals: list[UISwarmApprovalReference] = Field(min_length=1, max_length=8)


class UIApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=2_000)
    step_id: str | None = Field(default=None, min_length=1, max_length=40)
    challenge_id: str | None = Field(default=None, min_length=16, max_length=128)
    approvals: list[UISwarmApprovalReference] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def require_approval_evidence(self) -> "UIApprovalDecision":
        if self.decision == "approve" and not (
            (self.step_id and self.challenge_id) or self.approvals
        ):
            raise ValueError("approval challenge evidence is required")
        return self


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


def _model_catalog_evidence(
    jarvis: Any,
) -> tuple[set[str], bool, float | None]:
    """Return sanitized catalog IDs plus bounded monotonic freshness evidence."""
    raw_catalog = getattr(jarvis, "_model_catalog", set()) or set()
    try:
        live = {
            item.strip()
            for item in raw_catalog
            if isinstance(item, str) and item.strip() and len(item.strip()) <= 200
        }
    except TypeError:
        live = set()

    try:
        cached_at = float(getattr(jarvis, "_model_catalog_cached_at", 0.0) or 0.0)
    except (TypeError, ValueError, OverflowError):
        cached_at = 0.0
    age = time.monotonic() - cached_at if cached_at > 0.0 and math.isfinite(cached_at) else None
    if age is not None and not math.isfinite(age):
        age = None
    fresh = bool(
        live
        and age is not None
        and 0.0 <= age <= MODEL_CATALOG_TTL_SECONDS
    )
    return live, fresh, age


def _model_inventory(jarvis: Any, primary: str) -> list[dict[str, Any]]:
    """Merge configured knowledge with catalog availability without inventing health."""
    configured = {
        model.id: model
        for model in get_models_by_type(ModelType.CHAT)
        if not model.deprecated
    }
    live, catalog_fresh, catalog_age = _model_catalog_evidence(jarvis)
    routed = {
        model_id
        for candidates in ModelRouter.TASK_MODELS.values()
        for model_id in candidates
    }
    model_ids = set(configured) | live | routed | {primary}
    now = time.monotonic()
    disabled_until = getattr(jarvis, "_model_disabled_until", {})
    rows: list[dict[str, Any]] = []
    for model_id in sorted(model_ids, key=lambda value: (value != primary, value)):
        metadata = configured.get(model_id)
        in_catalog = model_id in live
        selectable = catalog_fresh and in_catalog and _looks_chat_compatible(model_id)
        cooling_down = float(disabled_until.get(model_id, 0.0) or 0.0) > now
        route_state = (
            "degraded" if selectable and cooling_down
            else "available" if selectable
            else "configured" if metadata is not None or model_id in routed
            else "unavailable"
        )
        rows.append({
            "id": model_id,
            "name": metadata.name if metadata else _model_name(model_id),
            "provider": _model_provider(model_id),
            "variants": 1,
            # Catalog membership proves routing availability, not successful
            # inference. Only a current cooldown is negative health evidence.
            "health": "degraded" if cooling_down else "unknown",
            "latencyMs": 0,
            "selectable": selectable,
            "catalogSource": (
                "live" if in_catalog and catalog_fresh
                else "stale_cache" if in_catalog and catalog_age is not None and catalog_age > MODEL_CATALOG_TTL_SECONDS
                else "cached_unverified" if in_catalog
                else "configured"
            ),
            "catalogFresh": bool(in_catalog and catalog_fresh),
            "catalogAgeSeconds": round(catalog_age, 1) if in_catalog and catalog_age is not None else None,
            "capabilityState": route_state,
            "evidenceSource": (
                "model.cooldown" if cooling_down
                else "nvidia.model_catalog" if in_catalog and catalog_fresh
                else "nvidia.model_catalog.stale" if in_catalog
                else "configured.model_metadata"
            ),
        })
    return rows


def _capability(
    capability_id: str,
    label: str,
    state: str,
    summary: str,
    *evidence: tuple[str, str],
) -> dict[str, Any]:
    """Build one bounded, evidence-citing capability digital-twin record."""
    if state not in CAPABILITY_STATES:
        raise ValueError(f"unsupported capability state: {state}")
    rows = [
        {"source": str(source)[:80], "detail": str(detail)[:240]}
        for source, detail in evidence
        if str(source).strip() and str(detail).strip()
    ]
    if not rows:
        raise ValueError("capability evidence is required")
    return {
        "id": capability_id,
        "label": label,
        "state": state,
        "summary": summary[:300],
        "evidence": rows[:6],
    }


def _read_mobile_access_record() -> dict[str, Any] | None:
    """Read non-secret tunnel publication metadata without probing the network."""
    try:
        value = json.loads(MOBILE_ACCESS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    origin = str(value.get("tunnel", "")).strip()
    public_url = str(value.get("url", "")).strip()
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or public_url != f"{origin}/mobile":
        return None
    updated_at = str(value.get("updated_at", "")).strip()
    try:
        published_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if published_at.tzinfo is None:
            published_at = published_at.astimezone()
        age_seconds = (datetime.now().astimezone() - published_at).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return None
    if age_seconds < -60 or age_seconds > MOBILE_ACCESS_TTL_SECONDS:
        return None
    return {
        "published": True,
        "scheme": parsed.scheme,
        "host_kind": "trycloudflare" if parsed.hostname.endswith(".trycloudflare.com") else "custom",
        "updated_at": updated_at[:64],
        "age_seconds": max(0.0, age_seconds),
    }


def _request_transport(request: Any) -> tuple[bool, bool, str]:
    """Describe only transport evidence visible on the current request."""
    headers = getattr(request, "headers", {}) or {}
    forwarded = str(headers.get("x-forwarded-proto", "") or "").split(",", 1)[0].strip()
    request_scheme = str(getattr(getattr(request, "url", None), "scheme", "") or "").strip()
    peer_host = str(getattr(getattr(request, "client", None), "host", "") or "").strip()
    scope = getattr(request, "scope", {}) or {}
    extensions = scope.get("extensions", {}) if isinstance(scope, dict) else {}
    scope_scheme = str(scope.get("scheme", "") if isinstance(scope, dict) else "").strip()
    explicit_tls_extension = bool(
        isinstance(extensions, dict) and extensions.get("tls")
        and request_scheme.casefold() in {"https", "wss"}
    )
    # Uvicorn derives ASGI scope["scheme"] from the actual socket transport.
    # A proxy middleware can also rewrite that field, so scheme-only evidence is
    # accepted as direct TLS only when no forwarding claim is present. Forwarded
    # HTTPS remains subject to the explicit trusted-peer policy below.
    uvicorn_direct_tls = bool(
        not forwarded
        and request_scheme.casefold() in {"https", "wss"}
        and scope_scheme.casefold() in {"https", "wss"}
    )
    direct_tls = explicit_tls_extension or uvicorn_direct_tls
    configured = config.get("security.trusted_proxy_hosts", ())
    if isinstance(configured, str):
        trusted_proxy_hosts = {
            host.strip() for host in configured.split(",") if host.strip()
        }
    else:
        trusted_proxy_hosts = {str(host).strip() for host in configured or () if str(host).strip()}
    trusted_forwarded = bool(
        peer_host and peer_host in trusted_proxy_hosts
        and forwarded.casefold() == "https"
    )
    https_indicated = (
        request_scheme.casefold() in {"https", "wss"}
        or scope_scheme.casefold() in {"https", "wss"}
        or forwarded.casefold() == "https"
    )
    secure = direct_tls or trusted_forwarded
    observed = request_scheme.casefold() or "unknown"
    if direct_tls:
        observed = f"{observed};direct_tls=true"
    if trusted_forwarded:
        observed = f"{observed};trusted_proxy=https"
    elif forwarded:
        observed = f"{observed};forwarded={forwarded.casefold()};untrusted"
    return secure, https_indicated, observed


def _capability_projection(
    *,
    request: Any,
    jarvis: Any,
    tool_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    provider_connected: bool,
    preferences: dict[str, Any],
    agent_status: dict[str, Any],
    knowledge: dict[str, Any],
    mobile_access: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Project code/config/runtime facts without promoting presence into health."""
    tool_names = {str(row.get("name", "")) for row in tool_rows}
    browser_adapter_tools = sorted(
        name for name in tool_names
        if name in {
            "browser_navigate", "browser_click", "browser_type", "browser_download",
            "browser_screenshot", "browser_session",
        }
    )
    selectable = [row for row in model_rows if row.get("selectable")]
    active_cooldowns = [
        row for row in model_rows if row.get("evidenceSource") == "model.cooldown"
    ]
    _catalog_ids, catalog_evidence_fresh, catalog_age = _model_catalog_evidence(jarvis)
    catalog_fresh = bool(selectable) and catalog_evidence_fresh
    stale_catalog = [
        row for row in model_rows
        if row.get("catalogSource") in {"stale_cache", "cached_unverified"}
    ]
    secure_request, https_indicated, observed_scheme = _request_transport(request)
    mobile_access = mobile_access if mobile_access is not None else _read_mobile_access_record()
    graph = knowledge.get("graph") if isinstance(knowledge.get("graph"), dict) else {}
    vault = knowledge.get("vault") if isinstance(knowledge.get("vault"), dict) else {}
    knowledge_available = knowledge.get("health") == "good"
    knowledge_partial = bool(int(graph.get("node_count", 0) or 0) or vault.get("exists"))

    if secure_request:
        remote_state = "verified"
        remote_summary = "The current dashboard request has explicit trusted HTTPS transport evidence."
    elif https_indicated or mobile_access:
        remote_state = "configured"
        remote_summary = (
            "HTTPS is indicated by runtime scope or a recent tunnel record, but transport and reachability are unverified."
        )
    else:
        remote_state = "unavailable"
        remote_summary = "No HTTPS transport evidence or published remote tunnel is visible to this runtime."

    if catalog_fresh:
        catalog_state = "verified"
        catalog_summary = f"A live NVIDIA catalog was fetched recently with {len(selectable)} selectable chat routes."
    elif stale_catalog:
        catalog_state = "degraded"
        catalog_summary = (
            f"{len(stale_catalog)} cached NVIDIA catalog routes remain visible as historical evidence, "
            "but freshness is expired or unverified and none are selectable."
        )
    elif provider_connected:
        catalog_state = "configured"
        catalog_summary = "The NVIDIA client is configured, but no selectable live catalog is cached."
    else:
        catalog_state = "unavailable"
        catalog_summary = "No provider client or selectable live model catalog is available."

    if not provider_connected:
        inference_state = "unavailable"
        inference_summary = "No NVIDIA provider client is constructed for inference."
    elif active_cooldowns:
        inference_state = "degraded"
        inference_summary = f"{len(active_cooldowns)} model route(s) are in a failure cooldown."
    else:
        inference_state = "available"
        inference_summary = "Inference is configured, but no durable active health probe is stored."

    auto_enabled = bool(preferences.get("auto_mode", True))
    auto_state = (
        "degraded" if auto_enabled and inference_state in {"degraded", "unavailable"}
        else "available" if auto_enabled
        else "configured"
    )
    auto_summary = (
        "Deterministic task routing is enabled; catalog and cooldown evidence guide selection, not live health scores."
        if auto_enabled
        else "Deterministic task routing is installed but disabled by operator preference."
    )

    capabilities = [
        _capability(
            "dashboard_projection", "Dashboard projection", "verified",
            "This snapshot was produced by the authenticated live control plane.",
            ("api.ui.snapshot", "The current request reached build_snapshot successfully."),
        ),
        _capability(
            "agent_worker", "Agent worker",
            "verified" if agent_status.get("worker_online") else "degraded",
            "The durable agent worker reports online." if agent_status.get("worker_online")
            else "The durable agent worker is not currently online.",
            ("agent_runtime.status", f"worker_online={bool(agent_status.get('worker_online'))}"),
        ),
        _capability(
            "tool_registry", "Guarded tool registry",
            "available" if tool_rows else "unavailable",
            f"{len(tool_rows)} tools are registered; registration is not an execution probe.",
            ("agent_runtime.list_tools", f"registered_count={len(tool_rows)}"),
        ),
        _capability(
            "web_search", "Web search",
            "available" if "web_search" in tool_names else "unavailable",
            "A guarded search tool is registered; no search was executed by this snapshot."
            if "web_search" in tool_names else "No guarded web search tool is registered.",
            ("agent.tool_registry", "web_search registered" if "web_search" in tool_names else "web_search absent"),
        ),
        _capability(
            "url_launcher", "URL launcher",
            "available" if "open_url" in tool_names else "unavailable",
            "The default-browser URL launcher is registered; it is not browser automation."
            if "open_url" in tool_names else "No URL-launch tool is registered.",
            ("agent.tool_registry", "open_url registered" if "open_url" in tool_names else "open_url absent"),
        ),
        _capability(
            "browser_automation", "Isolated browser automation",
            "available" if browser_adapter_tools else "unavailable",
            "An isolated browser action adapter is registered."
            if browser_adapter_tools else "No isolated browser session/action adapter is registered.",
            ("agent.tool_registry", ", ".join(browser_adapter_tools) if browser_adapter_tools else "no browser action adapter tools"),
        ),
        _capability(
            "model_catalog", "Model catalog", catalog_state, catalog_summary,
            ("jarvis.model_catalog", f"selectable_chat_routes={len(selectable)}"),
            ("jarvis.model_catalog", "cache_age_seconds=unknown" if catalog_age is None else f"cache_age_seconds={catalog_age:.1f}"),
        ),
        _capability(
            "model_inference", "Model inference", inference_state, inference_summary,
            ("jarvis.provider_client", f"configured={provider_connected}"),
            ("jarvis.model_cooldowns", f"active_count={len(active_cooldowns)}"),
            ("health_probe", "no durable active inference probe"),
        ),
        _capability(
            "auto_routing", "Auto model routing", auto_state, auto_summary,
            ("dashboard.preferences", f"auto_mode={auto_enabled}"),
            ("model_router", f"selectable_catalog_routes={len(selectable)}"),
        ),
        _capability(
            "remote_https", "Remote HTTPS", remote_state, remote_summary,
            ("current_request", f"observed_scheme={observed_scheme}"),
            ("mobile_access_record", "recent record present" if mobile_access else "no recent record"),
        ),
        _capability(
            "voice_authority", "Browser voice authority",
            "configured" if preferences.get("auto_mic", True) else "unavailable",
            "Voice capture is enabled by preference; browser permission and device readiness are client-observed."
            if preferences.get("auto_mic", True) else "Voice capture is disabled by operator preference.",
            ("dashboard.preferences", f"auto_mic={bool(preferences.get('auto_mic', True))}"),
            ("browser_runtime", "permission and device signal are not visible in this backend snapshot"),
        ),
        _capability(
            "knowledge_projection", "Graphify and Obsidian projection",
            "available" if knowledge_available else "degraded" if knowledge_partial else "unavailable",
            "Graph and vault artifacts are readable; availability does not prove commit freshness."
            if knowledge_available else "One or more knowledge projection artifacts are unavailable.",
            ("knowledge_vault.status", f"nodes={int(graph.get('node_count', 0) or 0)}"),
            ("knowledge_vault.status", f"vault_exists={bool(vault.get('exists'))}"),
        ),
    ]
    return capabilities


def _capability_map(capabilities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in capabilities}


def _capability_tone(capability: dict[str, Any]) -> str:
    return CAPABILITY_TONES[str(capability["state"])]


def _capability_item(capability: dict[str, Any]) -> dict[str, Any]:
    evidence = capability["evidence"][0]
    return {
        "name": capability["label"].upper(),
        "sub": capability["summary"],
        "tag": capability["state"].upper(),
        "tone": _capability_tone(capability),
        "pct": 0,
        "meta": [["EVIDENCE", str(evidence["source"]).upper()], ["STATE", capability["state"].upper()]],
    }


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


def _serialized_approval_reference(run: dict[str, Any]) -> dict[str, str] | None:
    pending = run.get("pending_approval")
    step = run.get("pending_step")
    if not isinstance(pending, dict) or not isinstance(step, dict):
        return None
    step_id = str(step.get("id", "")).strip()
    challenge_id = str(pending.get("challenge_id", "")).strip()
    bound_step_id = str(pending.get("step_id", "")).strip()
    if (
        not step_id or len(challenge_id) < 16
        or bound_step_id != step_id
    ):
        return None
    return {"stepId": step_id, "challengeId": challenge_id}


def _agent_card_action(run: dict[str, Any]) -> dict[str, Any] | None:
    """Return an explicit operator action for a durable agent card."""

    status = str(run.get("status", ""))
    run_id = str(run.get("id", ""))
    if not run_id:
        return None
    if status == "awaiting_confirmation":
        approval = _serialized_approval_reference(run)
        if approval is None:
            return None
        return {
            "command": "approve_agent_run",
            "payload": {"runId": run_id, **approval},
            "confirm": (
                f"Approve guarded step {approval['stepId']} under challenge "
                f"{approval['challengeId'][:8]}...?"
            ),
        }
    if status in ACTIVE_STATES | {"awaiting_confirmation", "stopping"}:
        return {
            "command": "cancel_agent_run",
            "payload": {"runId": run_id},
            "confirm": "Cancel this active agent run?",
        }
    return None


def _swarm_card_action(
    run: dict[str, Any],
    agent_runs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return an explicit operator action for a durable swarm card."""

    status = str(run.get("status", ""))
    run_id = str(run.get("id", ""))
    if not run_id:
        return None
    if status == "awaiting_confirmation":
        approvals: list[dict[str, str]] = []
        agent_runs = agent_runs or {}
        for task in run.get("tasks", []):
            if not isinstance(task, dict) or task.get("status") != "awaiting_confirmation":
                continue
            agent_run_id = str(task.get("agent_run_id", "")).strip()
            child = agent_runs.get(agent_run_id)
            approval = _serialized_approval_reference(child) if child else None
            if not agent_run_id or approval is None:
                return None
            approvals.append({"agentRunId": agent_run_id, **approval})
        if not approvals:
            return None
        return {
            "command": "approve_swarm_run",
            "payload": {"runId": run_id, "approvals": approvals},
            "confirm": (
                f"Approve {len(approvals)} guarded swarm step(s) under the "
                "displayed challenges and resume the mission?"
            ),
        }
    if status in ACTIVE_STATES | {"stopping"}:
        return {
            "command": "cancel_swarm_run",
            "payload": {"runId": run_id},
            "confirm": "Cancel this active swarm mission?",
        }
    return None


def _card_action_label(action: dict[str, Any] | None) -> str:
    command = str((action or {}).get("command", ""))
    if command.startswith("approve_"):
        return "APPROVE"
    if command.startswith("cancel_"):
        return "CANCEL"
    return "DETAIL"


async def _approve_agent_current_step(
    jarvis: Any,
    run_id: str,
    approval: UIAgentApprovalRequest,
) -> dict[str, Any]:
    run = jarvis.agent_runtime.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    if run.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail=f"Agent run is {run.status}, not awaiting confirmation")
    if not run.plan or run.current_step >= len(run.plan.steps):
        raise HTTPException(status_code=409, detail="Agent run has no pending step to approve")
    try:
        run = await jarvis.agent_runtime.approve(
            run_id, [approval.step_id], approval.challenge_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail=APPROVAL_CONFLICT_DETAIL,
        ) from exc
    return {
        "ok": True,
        "message": f"Approved guarded step {approval.step_id}; agent is now {run.status}",
        "runId": run.id,
        "status": run.status,
    }


async def _approve_swarm_current_steps(
    jarvis: Any,
    run_id: str,
    request: UISwarmApprovalRequest,
) -> dict[str, Any]:
    run = jarvis.swarm_runtime.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Swarm run not found")
    if run.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail=f"Swarm run is {run.status}, not awaiting confirmation")
    expected: dict[str, tuple[str, str]] = {}
    for task in run.tasks.values():
        if task.status != "awaiting_confirmation" or not task.agent_run_id:
            continue
        agent_run = jarvis.agent_runtime.get_run(task.agent_run_id)
        if (
            agent_run is None or agent_run.status != "awaiting_confirmation"
            or not agent_run.plan or agent_run.current_step >= len(agent_run.plan.steps)
            or agent_run.pending_approval is None
        ):
            raise HTTPException(status_code=409, detail=APPROVAL_CONFLICT_DETAIL)
        step = agent_run.plan.steps[agent_run.current_step]
        expected[agent_run.id] = (
            step.id, agent_run.pending_approval.challenge_id,
        )
    if not expected:
        raise HTTPException(status_code=409, detail="Swarm has no current guarded step to approve")
    supplied = {item.agent_run_id: item for item in request.approvals}
    if len(supplied) != len(request.approvals) or set(supplied) != set(expected):
        raise HTTPException(status_code=409, detail=APPROVAL_CONFLICT_DETAIL)
    for agent_run_id, (step_id, challenge_id) in expected.items():
        item = supplied[agent_run_id]
        if item.step_id != step_id or item.challenge_id != challenge_id:
            raise HTTPException(status_code=409, detail=APPROVAL_CONFLICT_DETAIL)

    applied_items: list[dict[str, str]] = []
    for agent_run_id in sorted(expected):
        item = supplied[agent_run_id]
        try:
            approved_run = await jarvis.agent_runtime.approve(
                agent_run_id, [item.step_id], item.challenge_id,
            )
        except (KeyError, ValueError) as exc:
            if not applied_items:
                if isinstance(exc, KeyError):
                    raise HTTPException(
                        status_code=404, detail="Linked agent run not found",
                    ) from exc
                raise HTTPException(
                    status_code=409, detail=APPROVAL_CONFLICT_DETAIL,
                ) from exc
            resume_status = "unknown"
            reconciliation_reason: str | None = None
            try:
                reconciled = await jarvis.swarm_runtime.resume(run_id)
                resume_status = str(reconciled.status)
            except (KeyError, ValueError, RuntimeError):
                resume_status = "failed"
                reconciliation_reason = SWARM_RESUME_CONFLICT_DETAIL
            receipt = swarm_approval_receipt(
                jarvis,
                run_id,
                applied_items=applied_items,
                requested_count=len(expected),
                code=SWARM_APPROVAL_PARTIAL_CODE,
                reason_code=APPROVAL_CONFLICT_DETAIL,
                ok=False,
                resume_attempted=True,
                failed_approval_id=f"{agent_run_id}:{item.step_id}",
                resume_status=resume_status,
                reconciliation_reason_code=reconciliation_reason,
            )
            receipt["message"] = (
                f"Applied {len(applied_items)} of {len(expected)} guarded swarm "
                "approval(s). Refresh mission status before any retry."
            )
            return JSONResponse(status_code=409, content=receipt)
        applied_items.append(approval_applied_item(
            agent_run_id, item.step_id, approved_run,
        ))
    try:
        run = await jarvis.swarm_runtime.resume(run_id)
    except (KeyError, ValueError, RuntimeError):
        receipt = swarm_approval_receipt(
            jarvis,
            run_id,
            applied_items=applied_items,
            requested_count=len(expected),
            code=SWARM_APPROVAL_PARTIAL_CODE,
            reason_code=SWARM_RESUME_CONFLICT_DETAIL,
            ok=False,
            resume_attempted=True,
            resume_status="failed",
            reconciliation_reason_code=SWARM_RESUME_CONFLICT_DETAIL,
        )
        receipt["message"] = (
            f"Applied {len(applied_items)} guarded swarm approval(s), but the "
            "mission could not be fully resumed. Refresh status before any retry."
        )
        return JSONResponse(status_code=409, content=receipt)
    receipt = swarm_approval_receipt(
        jarvis,
        run_id,
        applied_items=applied_items,
        requested_count=len(expected),
        code=SWARM_APPROVAL_APPLIED_CODE,
        reason_code=SWARM_APPROVAL_APPLIED_CODE,
        ok=True,
        resume_attempted=True,
        resume_status=str(run.status),
    )
    receipt.update({
        "ok": True,
        "message": f"Approved {len(applied_items)} guarded swarm step(s); mission is now {run.status}",
        "runId": run.id,
        "status": run.status,
        "swarm_status": run.status,
    })
    return receipt


def _require_dynamic_scope(principal: OperatorPrincipal, scope: str) -> None:
    if principal is None or scope not in principal.scopes:
        raise HTTPException(status_code=403, detail="scope_required")


async def _decide_run_approval(
    jarvis: Any,
    approval_id: str,
    decision: str,
    *,
    step_id: str | None = None,
    challenge_id: str | None = None,
    approvals: list[UISwarmApprovalReference] | None = None,
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
            if not step_id or not challenge_id:
                raise HTTPException(status_code=409, detail=APPROVAL_CONFLICT_DETAIL)
            return await _approve_agent_current_step(
                jarvis,
                approval_id,
                UIAgentApprovalRequest(
                    step_id=step_id,
                    challenge_id=challenge_id,
                ),
            )
        if not approvals:
            raise HTTPException(status_code=409, detail=APPROVAL_CONFLICT_DETAIL)
        return await _approve_swarm_current_steps(
            jarvis,
            approval_id,
            UISwarmApprovalRequest(approvals=approvals),
        )
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
    agent_runs_by_id = {
        str(run.get("id")): run for run in agent_runs if run.get("id")
    }
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
    jarvis_status = jarvis.get_status()
    provider_connected = bool(jarvis_status.get("nvidia_connected"))
    project_rows = jarvis.workspace_registry.list()
    tool_rows = jarvis.agent_runtime.list_tools()
    schedule_rows = jarvis.agent_runtime.list_schedules()
    skill_rows = jarvis.get_available_skills()
    capabilities = _capability_projection(
        request=request,
        jarvis=jarvis,
        tool_rows=tool_rows,
        model_rows=model_rows,
        provider_connected=provider_connected,
        preferences=preferences,
        agent_status=agent_status,
        knowledge=knowledge,
    )
    capability_by_id = _capability_map(capabilities)
    model_inference = capability_by_id["model_inference"]
    model_catalog = capability_by_id["model_catalog"]
    auto_routing = capability_by_id["auto_routing"]
    remote_https = capability_by_id["remote_https"]
    voice_authority = capability_by_id["voice_authority"]
    browser_search = capability_by_id["web_search"]
    url_launcher = capability_by_id["url_launcher"]
    browser_automation = capability_by_id["browser_automation"]
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
                    ["ACTION", _card_action_label(_agent_card_action(r))],
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
                    ["ACTION", _card_action_label(_swarm_card_action(r, agent_runs_by_id))],
                ],
                "action": _swarm_card_action(r, agent_runs_by_id),
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
                {"k": "CONFIG", "v": "CONFIGURED" if vault["obsidian_configured"] else "MISSING", "tone": "info" if vault["obsidian_configured"] else "warn"},
                {"k": "HEALTH", "v": knowledge["health"].upper(), "tone": "ok" if knowledge["health"] == "good" else "warn"},
            ],
            "items": [{
                "name": "JARVIS VAULT", "sub": str(vault["path"]),
                "tag": "ONLINE" if vault["exists"] else "MISSING", "tone": "ok" if vault["exists"] else "danger",
                "pct": 0, "meta": [["MARKDOWN", str(vault["markdown_count"])], ["CONFIG", "YES" if vault["obsidian_configured"] else "NO"]],
            }],
        },
        "BROWSER": {
            "title": "BROWSER CAPABILITIES", "subtitle": "Registration and runtime evidence are reported separately",
            "kpis": [
                {"k": "SEARCH", "v": browser_search["state"].upper(), "tone": _capability_tone(browser_search)},
                {"k": "URL LAUNCH", "v": url_launcher["state"].upper(), "tone": _capability_tone(url_launcher)},
                {"k": "AUTOMATION", "v": browser_automation["state"].upper(), "tone": _capability_tone(browser_automation)},
            ],
            "items": [
                _capability_item(browser_search),
                _capability_item(url_launcher),
                _capability_item(browser_automation),
            ],
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
                "tone": "warn" if row["risk"] == "write" else "info", "pct": 0,
                "meta": [["EVIDENCE", "TOOL REGISTRY"], ["STATUS", "AVAILABLE"]],
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
                    ["ACTION", _card_action_label(_agent_card_action(run))],
                ],
                "action": _agent_card_action(run),
            } for run in agent_runs[:20]],
        },
        "TOOLS": {
            "title": "GUARDED TOOL REGISTRY", "subtitle": "Registered capabilities; execution health requires separate evidence",
            "kpis": [
                {"k": "TOTAL", "v": str(len(tool_rows)), "tone": "info"},
                {"k": "READ", "v": str(sum(row["risk"] == "read" for row in tool_rows)), "tone": "ok"},
                {"k": "WRITE", "v": str(sum(row["risk"] == "write" for row in tool_rows)), "tone": "warn"},
                {"k": "SKILLS", "v": str(len(skill_rows)), "tone": "info"},
            ],
            "items": [{
                "name": row["name"].upper(), "sub": row["description"], "tag": "AVAILABLE",
                "tone": "warn" if row["risk"] == "write" else "info", "pct": 0,
                "meta": [["EVIDENCE", "TOOL REGISTRY"], ["POLICY", "CONFIRM" if row["risk"] == "write" else "ALLOW"]],
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
                "name": "NVIDIA NIM", "sub": model_inference["summary"],
                "tag": model_inference["state"].upper(), "tone": _capability_tone(model_inference), "pct": 0,
                "meta": [["CATALOG", model_catalog["state"].upper()], ["METERING", "UNAVAILABLE"]],
            }],
        },
        "DEVICES": {
            "title": "DEVICE CHANNELS", "subtitle": "Browser-selected microphone and system output",
            "kpis": [
                {"k": "VOICE", "v": voice_authority["state"].upper(), "tone": _capability_tone(voice_authority)},
                {"k": "HOST", "v": platform.node().upper(), "tone": "info"},
                {"k": "REMOTE HTTPS", "v": remote_https["state"].upper(), "tone": _capability_tone(remote_https)},
            ],
            "items": [
                _capability_item(voice_authority),
                _capability_item(remote_https),
                {"name": "SPEAKER PROFILE", "sub": "A browser output profile is configured; playback readiness is client-observed.", "tag": "CONFIGURED", "tone": "muted", "pct": 0, "meta": [["VOICE", str(preferences.get("voice_profile", "en-GB"))], ["EVIDENCE", "PREFERENCE"]]},
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
                {"name": "AUTO ROUTING", "sub": auto_routing["summary"], "tag": auto_routing["state"].upper(), "tone": _capability_tone(auto_routing), "pct": 0, "meta": [["PRIMARY", primary], ["CATALOG", model_catalog["state"].upper()]]},
                _capability_item(voice_authority),
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
            {"name": "UI INTERFACE", "state": capability_by_id["dashboard_projection"]["state"].upper(), "tone": _capability_tone(capability_by_id["dashboard_projection"])},
            {"name": "AGENT CORE", "state": capability_by_id["agent_worker"]["state"].upper(), "tone": _capability_tone(capability_by_id["agent_worker"])},
            {"name": "VOICE SYSTEM", "state": voice_authority["state"].upper(), "tone": _capability_tone(voice_authority)},
            {"name": "API ROUTER", "state": auto_routing["state"].upper(), "tone": _capability_tone(auto_routing)},
            {"name": "BRAIN GRAPH", "state": capability_by_id["knowledge_projection"]["state"].upper(), "tone": _capability_tone(capability_by_id["knowledge_projection"])},
        ],
        "graph": {"nodes": graph["node_count"], "edges": graph["edge_count"], "vaultNotes": vault["markdown_count"], "health": "healthy" if knowledge["health"] == "good" else "degraded"},
        "router": {
            "auto": bool(preferences.get("auto_mode", True)), "primary": primary,
            "models": model_rows, "capabilityState": auto_routing["state"],
            "evidence": auto_routing["evidence"],
        },
        "providers": [{
            "id": "nvidia", "name": "NVIDIA NIM",
            "status": "degraded" if model_inference["state"] == "degraded" else "down" if model_inference["state"] == "unavailable" else "unknown",
            "latencyMs": 0, "latencyVerified": False,
            "circuit": "unknown",
            "capabilityState": model_inference["state"],
            "evidence": model_inference["evidence"],
        }],
        "voice": {
            "armed": bool(preferences.get("auto_mic", True)),
            "inputDevice": "Browser selected input", "outputDevice": "System default",
            "profile": str(preferences.get("voice_profile", "en-GB")),
            "sensitivity": int(preferences.get("sensitivity", 6)), "level": 0,
            "capabilityState": voice_authority["state"],
        },
        "usage": {"requests": sum(item.get("role") == "assistant" for item in history), "tokens": 0, "spendUsd": 0, "capUsd": 0, "metered": False, "series": []},
        "events": _events(history, agent_runs, swarm_runs), "screens": screens, "viz": viz,
        "capabilities": capabilities,
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
        step_id=decision.step_id,
        challenge_id=decision.challenge_id,
        approvals=decision.approvals,
    )


@router.post("/agent/runs/{run_id}/approve-current")
async def approve_agent_current_step(
    run_id: str,
    approval: UIAgentApprovalRequest,
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(APPROVALS_WRITE)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    """Approve exactly the currently pending agent step under the approval scope."""
    return await _approve_agent_current_step(_jarvis(request), run_id, approval)


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
    approval: UISwarmApprovalRequest,
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(APPROVALS_WRITE)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    """Approve one current guarded step per waiting child, then resume the swarm."""
    return await _approve_swarm_current_steps(_jarvis(request), run_id, approval)


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
        approvals = []
        raw_approvals = payload.get("approvals")
        if isinstance(raw_approvals, list):
            try:
                approvals = [
                    UISwarmApprovalReference.model_validate(item)
                    for item in raw_approvals
                ]
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=422, detail="Invalid approval references",
                ) from exc
        return await _decide_run_approval(
            jarvis,
            approval_id,
            command.action,
            step_id=str(payload.get("step_id") or payload.get("stepId") or "").strip() or None,
            challenge_id=str(payload.get("challenge_id") or payload.get("challengeId") or "").strip() or None,
            approvals=approvals,
        )
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
            raise HTTPException(
                status_code=409,
                detail="The NVIDIA model catalog is not ready; fresh evidence is unavailable",
            )
        if model not in selectable:
            raise HTTPException(status_code=409, detail="Model is not a currently selectable chat-compatible NVIDIA route")
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
