"""Stateful, guarded agent runtime for JARVIS."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, TYPE_CHECKING

from pydantic import BaseModel, Field

from src.clients.provider_factory import ProviderSafeError
from src.config import config
from src.core.agent_store import AgentStore
from src.core.control import ControlBlockedError, ControlService, ControlState, StopGuard
from src.skills.nvidia_catalog import NvidiaSkillsCatalog

if TYPE_CHECKING:
    from src.core.jarvis import Jarvis

logger = logging.getLogger(__name__)


class ToolProcessError(RuntimeError):
    """A bounded tool process returned an exit code that was not allowed."""

    def __init__(self, exit_code: int):
        self.exit_code = int(exit_code)
        super().__init__(f"tool process exited with code {self.exit_code}")


class ToolCapabilityError(PermissionError):
    """A run attempted to plan or execute a tool outside its capability boundary."""

    def __init__(self, tool: str):
        self.tool = str(tool)
        super().__init__("tool is outside this run's capability profile")


class AgentStep(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=500)
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = "Useful evidence for the final answer"


class AgentPlan(BaseModel):
    goal: str
    summary: str = Field(min_length=1, max_length=800)
    steps: list[AgentStep] = Field(min_length=1, max_length=12)


@dataclass
class AgentRun:
    id: str
    goal: str
    model: str
    requested_model: str = "auto"
    autonomy: str = "guarded"
    max_steps: int = 8
    max_retries: int = 2
    attempts: int = 0
    schedule_id: str | None = None
    workspace_root: str | None = None
    capability_profile: str = "unrestricted"
    allowed_tools: set[str] | None = None
    record_conversation: bool = True
    status: str = "planning"
    plan: AgentPlan | None = None
    current_step: int = 0
    approved_steps: set[str] = field(default_factory=set)
    events: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    result: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "goal": self.goal, "model": self.model, "status": self.status,
            "requested_model": self.requested_model, "autonomy": self.autonomy,
            "max_steps": self.max_steps, "max_retries": self.max_retries,
            "attempts": self.attempts, "schedule_id": self.schedule_id,
            "workspace_root": self.workspace_root,
            "capability_profile": self.capability_profile,
            "allowed_tools": sorted(self.allowed_tools) if self.allowed_tools is not None else None,
            "record_conversation": self.record_conversation,
            "plan": self.plan.model_dump() if self.plan else None, "current_step": self.current_step,
            "events": self.events, "observations": self.observations, "result": self.result,
            "error": self.error, "created_at": self.created_at, "updated_at": self.updated_at,
            "pending_step": self.plan.steps[self.current_step].model_dump()
            if self.status == "awaiting_confirmation" and self.plan and self.current_step < len(self.plan.steps) else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentRun":
        plan = AgentPlan.model_validate(payload["plan"]) if payload.get("plan") else None
        return cls(
            id=payload["id"], goal=payload["goal"], model=payload.get("model", "auto"),
            requested_model=payload.get("requested_model", payload.get("model", "auto")),
            autonomy=payload.get("autonomy", "guarded"), max_steps=int(payload.get("max_steps", 8)),
            max_retries=int(payload.get("max_retries", 2)), attempts=int(payload.get("attempts", 0)),
            schedule_id=payload.get("schedule_id"), status=payload.get("status", "queued"), plan=plan,
            workspace_root=payload.get("workspace_root"),
            capability_profile=payload.get("capability_profile", "unrestricted"),
            allowed_tools=(
                set(payload.get("allowed_tools") or [])
                if payload.get("allowed_tools") is not None
                else None
            ),
            record_conversation=bool(payload.get("record_conversation", True)),
            current_step=int(payload.get("current_step", 0)),
            approved_steps=set(payload.get("approved_steps", [])), events=list(payload.get("events", [])),
            observations=list(payload.get("observations", [])), result=payload.get("result", ""),
            error=payload.get("error", ""), created_at=payload.get("created_at", datetime.now().isoformat()),
            updated_at=payload.get("updated_at", datetime.now().isoformat()),
        )


class AgentRuntime:
    """Plan, execute guarded tools, observe results, and synthesize an answer."""

    READ_TOOLS = {
        "system_info", "web_search", "calculator", "memory_search", "nvidia_skill_search",
        "notes_search", "calendar_list", "reminders_list", "workspace_list", "workspace_read",
        "workspace_search", "git_status", "github_status", "github_repo_view",
    }
    STATUS_RECEIPT_TOOLS = {"system_info", "git_status", "github_status"}
    CONTENT_READ_TOOLS = READ_TOOLS - STATUS_RECEIPT_TOOLS
    WRITE_TOOLS = {
        "note_create", "reminder_set", "calendar_create", "workspace_write",
        "workspace_patch", "command_run", "project_create", "git_init", "git_commit",
        "directory_create", "git_clone", "app_launch", "open_path", "open_url",
        "github_create_repo", "github_push", "github_issue_create", "github_pr_create",
    }
    REMOTE_WRITE_TOOLS = {
        "github_create_repo", "github_push", "github_issue_create", "github_pr_create",
    }
    LOCAL_EXECUTION_TOOLS = {"command_run", "app_launch"}
    WORKSPACE_AUTHOR_TOOLS = {
        "workspace_write", "workspace_patch", "directory_create", "project_create",
        "git_clone", "git_init", "git_commit",
    }
    DEVOPS_TOOLS = WORKSPACE_AUTHOR_TOOLS | LOCAL_EXECUTION_TOOLS | REMOTE_WRITE_TOOLS | {
        "open_path", "open_url",
    }
    CAPABILITY_PROFILES = {
        "read_only": frozenset(READ_TOOLS),
        "workspace_writer": frozenset(READ_TOOLS | WORKSPACE_AUTHOR_TOOLS),
        "devops": frozenset(READ_TOOLS | DEVOPS_TOOLS),
    }
    BLOCKED_APP_LAUNCHERS = frozenset({
        "powershell", "pwsh", "cmd", "wscript", "cscript", "mshta",
        "rundll32", "regsvr32",
    })
    TOOL_DESCRIPTIONS = {
        "system_info": "Read system status. arguments: action=info|cpu|memory|disk|processes|uptime|network",
        "web_search": "Search the public web. arguments: query",
        "calculator": "Safely calculate an expression. arguments: expression",
        "memory_search": "Search Ahmed's Jarvis memory. arguments: query, limit",
        "nvidia_skill_search": "Search installed NVIDIA skills. arguments: query, limit",
        "notes_search": "Search or list local notes. arguments: query (optional)",
        "calendar_list": "List local calendar events. arguments: day (optional)",
        "reminders_list": "List local reminders. arguments: none",
        "note_create": "Create a local note. REQUIRES CONFIRMATION. arguments: title, content",
        "reminder_set": "Create a local reminder. REQUIRES CONFIRMATION. arguments: text, when",
        "calendar_create": "Create a local calendar event. REQUIRES CONFIRMATION. arguments: title, day, time, duration",
        "workspace_list": "List files inside the configured coding workspace. arguments: path (optional)",
        "workspace_read": "Read a UTF-8 text file in the coding workspace. arguments: path, start_line (optional), end_line (optional)",
        "workspace_search": "Search workspace text with ripgrep. arguments: query, path (optional), glob (optional)",
        "git_status": "Read git working-tree status and recent diff summary. arguments: path (optional)",
        "workspace_write": "Create or replace a workspace text file. arguments: path, content. Protected outside Full Auto.",
        "workspace_patch": "Apply an exact text replacement in a workspace file. arguments: path, old_text, new_text. Protected outside Full Auto.",
        "command_run": "Run a bounded PowerShell command in the workspace. arguments: command, timeout_seconds, path (optional working directory). Always requires confirmation.",
        "directory_create": "Create a directory inside the active workspace. arguments: path. Protected outside Full Auto.",
        "project_create": "Create a real local starter project. arguments: name, kind=website|python, description (optional), directory (optional). Protected outside Full Auto.",
        "git_clone": "Clone a Git repository into the active workspace. arguments: repository, directory (optional). Protected outside Full Auto.",
        "git_init": "Initialize Git in a project folder. arguments: path (optional, defaults to workspace). Protected outside Full Auto.",
        "git_commit": "Commit current local project changes. arguments: message, path (optional). Protected outside Full Auto.",
        "github_status": "Check whether the locally installed GitHub CLI is authenticated. arguments: none.",
        "github_repo_view": "Read GitHub repository metadata. arguments: repository (optional, defaults to current repo).",
        "github_create_repo": "Create a GitHub repository from a local Git project. arguments: name, visibility=private|public, path (optional). Full Auto executes only when the goal explicitly requests GitHub publication.",
        "github_push": "Push the current Git branch to its configured GitHub remote. arguments: path (optional). Full Auto executes only when the goal explicitly requests a push or publication.",
        "github_issue_create": "Create a GitHub issue. arguments: title, body, repository (optional). Full Auto requires an explicit issue-creation goal.",
        "github_pr_create": "Create a GitHub pull request. arguments: title, body, base (optional), path (optional). Full Auto requires an explicit pull-request goal.",
        "app_launch": "Launch an installed Windows application by executable name. arguments: app, arguments (optional list). Always requires confirmation; shell and script-host executables are blocked.",
        "open_path": "Open a file or folder from the active workspace with Windows. arguments: path. Protected outside Full Auto.",
        "open_url": "Open an http/https URL in the default browser. arguments: url. Protected outside Full Auto.",
    }

    ACTION_PATTERN = re.compile(
        r"\b(create|build|make|scaffold|implement|fix|edit|change|update|write|save|"
        r"read|search|find|show|run|execute|install|test|debug|check|inspect|list|clone|commit|push|"
        r"publish|deploy|open|launch|delete|remove|rename|copy|move|generate|download|set up|setup)\b",
        flags=re.IGNORECASE,
    )
    FILE_CODE_CONTEXT_PATTERN = re.compile(
        r"```|\b(file|files|folder|folders|directory|directories|filesystem|workspace|code|codebase|"
        r"script|python|javascript|typescript|powershell|bash|shell|command|repo|repository|github|git|"
        r"website|web app|application|app|project|dashboard|test|tests|pytest|npm|node|build)\b|"
        r"\b[A-Za-z0-9_.-]+\.(?:py|js|jsx|ts|tsx|html|css|json|ya?ml|toml|md|txt|ps1|sh|sql)\b",
        flags=re.IGNORECASE,
    )
    SENSITIVE_FIELD_PATTERN = re.compile(
        r"^(?:(?:[a-z0-9]+)[_-])*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|passwd|secret|"
        r"credential|cookie|session[_-]?token)$",
        flags=re.IGNORECASE,
    )
    ADAPTIVE_PATTERN = re.compile(
        r"\b(build|scaffold|implement|fix|edit|change|update|test|debug|install|"
        r"deploy|website|web app|project|codebase)\b",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        jarvis: "Jarvis",
        store_path: Path | None = None,
        *,
        control_service: ControlService | None = None,
    ):
        self.jarvis = jarvis
        self.control_service = control_service
        self.stop_guard = StopGuard(control_service) if control_service is not None else None
        self.runs: dict[str, AgentRun] = {}
        self.nvidia_skills = NvidiaSkillsCatalog()
        project_root = Path(__file__).resolve().parents[2]
        self.workspace_root = Path(config.get("agent.workspace_root", str(project_root))).expanduser().resolve()
        database = store_path or Path(config.get("agent.database", str(project_root / "data" / "agent.db")))
        self.store = AgentStore(Path(database))
        self.schedules: dict[str, dict[str, Any]] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._scheduler_task: asyncio.Task | None = None
        self._run_tasks: dict[str, asyncio.Task] = {}
        self._started = False

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": name, "description": description, "risk": "write" if name in self.WRITE_TOOLS else "read"}
            for name, description in self.TOOL_DESCRIPTIONS.items()
        ]

    @classmethod
    def _resolve_capabilities(
        cls,
        allowed_tools: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None,
        capability_profile: str | None,
    ) -> tuple[set[str] | None, str]:
        """Resolve a durable, least-privilege tool boundary for one agent run."""
        known_tools = set(cls.TOOL_DESCRIPTIONS)
        profile_name = (capability_profile or "unrestricted").strip().casefold()
        if profile_name == "unrestricted":
            profile_tools: set[str] | None = None
        else:
            profile = cls.CAPABILITY_PROFILES.get(profile_name)
            if profile is None:
                raise ValueError("unknown capability profile")
            profile_tools = set(profile)

        if allowed_tools is None:
            effective = profile_tools
        else:
            requested = {str(tool).strip() for tool in allowed_tools if str(tool).strip()}
            unknown = requested - known_tools
            if unknown:
                raise ValueError("allowed_tools contains an unknown tool")
            effective = requested if profile_tools is None else requested & profile_tools
        return (None if effective is None else set(effective)), profile_name

    @classmethod
    def _tool_is_allowed(cls, allowed_tools: set[str] | None, tool: str | None) -> bool:
        return tool is None or allowed_tools is None or tool in allowed_tools

    @classmethod
    def _require_tool_allowed(cls, run: AgentRun, tool: str | None) -> None:
        if not cls._tool_is_allowed(run.allowed_tools, tool):
            raise ToolCapabilityError(str(tool))

    def get_run(self, run_id: str) -> AgentRun | None:
        return self.runs.get(run_id)

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        items = sorted(self.runs.values(), key=lambda item: item.updated_at, reverse=True)
        return [run.to_dict() for run in items[: max(1, min(limit, 250))]]

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for payload in self.store.load_runs():
            run = AgentRun.from_dict(payload)
            self.runs[run.id] = run
            if run.status in {"queued", "planning", "running", "synthesizing"}:
                if not self._effect_allowed(run, "recovery"):
                    continue
                run.status = "queued"
                run.error = ""
                self._event(run, "recovery", "queued", "Recovered unfinished run after restart")
                await self._queue.put(run.id)
        self.schedules = {item["id"]: item for item in self.store.load_schedules()}
        self._worker_task = asyncio.create_task(self._worker_loop(), name="jarvis-agent-worker")
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(), name="jarvis-agent-scheduler")

    async def shutdown(self) -> None:
        self._started = False
        for task in [self._worker_task, self._scheduler_task, *self._run_tasks.values()]:
            if task and not task.done():
                task.cancel()
        tasks = [task for task in [self._worker_task, self._scheduler_task, *self._run_tasks.values()] if task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._run_tasks.clear()

    def status(self) -> dict[str, Any]:
        active = sum(run.status in {"queued", "planning", "running", "synthesizing"} for run in self.runs.values())
        return {
            "started": self._started,
            "worker_online": bool(self._worker_task and not self._worker_task.done()),
            "scheduler_online": bool(self._scheduler_task and not self._scheduler_task.done()),
            "active_runs": active,
            "queued_runs": self._queue.qsize(),
            "durable_runs": len(self.runs),
            "schedules": len(self.schedules),
            "workspace_root": str(self.workspace_root),
            "autonomy_modes": ["guarded", "full"],
        }

    async def run(
        self, goal: str, model: str = "auto", max_steps: int = 8,
        autonomy: str = "guarded", max_retries: int = 2,
        workspace_root: str | Path | None = None,
        allowed_tools: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None = None,
        capability_profile: str | None = None,
        record_conversation: bool = True,
    ) -> AgentRun:
        """Execute inline for compatibility with CLI/tests."""
        self._require_global_effect("run_launch")
        run = self._new_run(
            goal, model, max_steps, autonomy, max_retries, workspace_root,
            allowed_tools, capability_profile, record_conversation,
        )
        self.runs[run.id] = run
        self._prune_runs()
        await self._run_existing(run)
        return run

    async def submit(
        self, goal: str, model: str = "auto", max_steps: int = 8,
        autonomy: str = "guarded", max_retries: int = 2,
        workspace_root: str | Path | None = None,
        allowed_tools: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None = None,
        capability_profile: str | None = None,
        record_conversation: bool = True,
    ) -> AgentRun:
        """Persist and enqueue work, returning immediately."""
        await self.start()
        self._require_global_effect("run_launch")
        run = self._new_run(
            goal, model, max_steps, autonomy, max_retries, workspace_root,
            allowed_tools, capability_profile, record_conversation,
        )
        self.runs[run.id] = run
        self._event(run, "queue", "queued", "Goal accepted by the durable agent queue")
        await self._queue.put(run.id)
        self._prune_runs()
        return run

    def _new_run(
        self, goal: str, model: str, max_steps: int, autonomy: str,
        max_retries: int, workspace_root: str | Path | None = None,
        allowed_tools: set[str] | frozenset[str] | list[str] | tuple[str, ...] | None = None,
        capability_profile: str | None = None,
        record_conversation: bool = True,
    ) -> AgentRun:
        mode = "full" if autonomy == "full" else "guarded"
        resolved_workspace = self._resolve_workspace_root(workspace_root)
        effective_tools, profile_name = self._resolve_capabilities(
            allowed_tools, capability_profile,
        )
        return AgentRun(
            id=f"agent-{uuid.uuid4().hex[:12]}", goal=goal, model=model,
            requested_model=model, autonomy=mode, max_steps=max(1, min(max_steps, 12)),
            max_retries=max(0, min(max_retries, 5)), status="queued",
            workspace_root=str(resolved_workspace),
            capability_profile=profile_name, allowed_tools=effective_tools,
            record_conversation=bool(record_conversation),
        )

    async def _run_existing(self, run: AgentRun) -> None:
        try:
            if not self._effect_allowed(run, "run_launch"):
                return
            if run.model == "auto" or not run.plan:
                if not self._effect_allowed(run, "provider"):
                    return
                routing = await self.jarvis.route_model(run.goal, run.requested_model)
                run.model = routing.model
            self._event(run, "planning", "start", "Building a guarded execution plan")
            if not run.plan:
                run.status = "planning"
                run.plan = await self._with_retry(
                    run, "planning", lambda: self._create_plan(
                        run.goal, run.model, run.max_steps, run.allowed_tools,
                    )
                )
            self._event(run, "planning", "end", run.plan.summary, {"steps": len(run.plan.steps)})
            await self._execute(run)
        except ControlBlockedError:
            # The guard already persisted a safe paused/stopping state and audit event.
            return
        except Exception as exc:
            code = self._safe_error_code(exc)
            logger.error("Agent run failed with safe code %s", code)
            run.status = "failed"; run.error = code; run.updated_at = datetime.now().isoformat()
            self._event(run, "run", "error", "Agent run failed", {"code": code})

    async def _worker_loop(self) -> None:
        while self._started:
            run_id = await self._queue.get()
            try:
                run = self.runs.get(run_id)
                if run and run.status == "queued":
                    task = asyncio.create_task(self._run_existing(run), name=f"jarvis-{run_id}")
                    self._run_tasks[run_id] = task
                    await task
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Autonomous worker failed for %s", run_id)
            finally:
                self._run_tasks.pop(run_id, None)
                self._queue.task_done()

    async def _with_retry(self, run: AgentRun, stage: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        last_error: Exception | None = None
        for attempt in range(run.max_retries + 1):
            if not self._effect_allowed(run, "retry"):
                raise ControlBlockedError("control_blocked")
            try:
                return await asyncio.wait_for(operation(), timeout=120)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                run.attempts += 1
                self._event(
                    run,
                    stage,
                    "retry",
                    f"Attempt {attempt + 1} failed",
                    {"code": self._safe_error_code(exc)},
                )
                if attempt < run.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 8))
        if isinstance(last_error, ToolProcessError):
            raise last_error
        raise RuntimeError(f"{stage.replace(':', '_')}_failed") from last_error

    async def approve(self, run_id: str, step_ids: list[str]) -> AgentRun:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.status != "awaiting_confirmation":
            return run
        run.approved_steps.update(step_ids)
        self._event(run, "approval", "granted", "Ahmed approved the pending action", {"steps": step_ids})
        await self._execute(run)
        return run

    def cancel(self, run_id: str) -> AgentRun:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.status not in {"completed", "failed", "cancelled"}:
            if self.control_service is None:
                run.status = "cancelled"
                event_type, message = "cancelled", "Run cancelled"
            else:
                # Cooperative cancellation is a signal, never descendant-stop proof.
                run.status = "stopping"
                event_type, message = "stopping", "Run cancellation requested"
            run.updated_at = datetime.now().isoformat()
            self._event(run, "run", event_type, message)
            task = self._run_tasks.get(run_id)
            if task and not task.done():
                task.cancel()
        return run

    async def _create_plan(
        self, goal: str, model: str, max_steps: int,
        allowed_tools: set[str] | None = None,
    ) -> AgentPlan:
        valid_tools = set(self.TOOL_DESCRIPTIONS) if allowed_tools is None else set(allowed_tools)
        deterministic = self._fallback_plan(goal)
        deterministic_has_tools = any(step.tool for step in deterministic.steps)
        deterministic_is_allowed = all(
            self._tool_is_allowed(allowed_tools, step.tool)
            for step in deterministic.steps
        )
        if deterministic_has_tools and deterministic_is_allowed:
            deterministic.steps = deterministic.steps[: max(1, min(max_steps, 12))]
            return deterministic
        tools = "\n".join(
            f"- {name}: {description}"
            for name, description in self.TOOL_DESCRIPTIONS.items()
            if name in valid_tools
        ) or "- No tools are authorized; provide analysis only and do not claim state changes."
        prompt = f"""You are the planning core for JARVIS, Ahmed's personal agentic AI.
Create an execution-first plan for the user's goal. If Ahmed asks to create, change, run, test,
publish, open, or operate something, you MUST use tools and produce verifiable effects rather
than advice. Inspect the workspace before editing unfamiliar code, make the smallest useful
change, and finish with a test or status check. Never invent tool names. In Guarded mode,
write/command tools pause for Ahmed. In Full Auto mode, explicitly requested local and GitHub
actions may execute automatically under hard safety limits. Limit the plan to {max(1, min(max_steps, 12))} steps.

Available tools:
{tools}

Return JSON only with this schema:
{{"goal":"...","summary":"...","steps":[{{"id":"step-1","description":"...","tool":null,"arguments":{{}},"expected_output":"..."}}]}}

User goal: {goal}"""
        try:
            client = await self.jarvis._require_provider_client()
            response = await client.chat_completion(
                [{"role": "system", "content": "Produce strict JSON plans. Do not include markdown fences."}, {"role": "user", "content": prompt}],
                model=model, temperature=0.1, max_tokens=1400,
            )
            raw = response["choices"][0]["message"]["content"]
            plan = AgentPlan.model_validate(self._parse_json(raw))
            for step in plan.steps:
                if step.tool and step.tool not in valid_tools:
                    raise ToolCapabilityError(step.tool)
            plan.steps = plan.steps[: max(1, min(max_steps, 12))]
            if self._needs_execution_plan(goal, plan):
                return self._capability_safe_fallback(goal, allowed_tools, max_steps)
            return plan
        except Exception as exc:
            logger.warning(
                "Planner output was invalid; using deterministic fallback (%s)",
                self._safe_error_code(exc),
            )
            return self._capability_safe_fallback(goal, allowed_tools, max_steps)

    def _capability_safe_fallback(
        self, goal: str, allowed_tools: set[str] | None, max_steps: int,
    ) -> AgentPlan:
        """Discard forbidden fallback actions while retaining any authorized evidence steps."""
        fallback = self._fallback_plan(goal)
        fallback.steps = [
            step for step in fallback.steps
            if self._tool_is_allowed(allowed_tools, step.tool)
        ][: max(1, min(max_steps, 12))]
        if not fallback.steps:
            fallback = AgentPlan(
                goal=goal,
                summary="Analyze the assignment within the run's capability boundary.",
                steps=[AgentStep(
                    id="step-1",
                    description="Analyze the assignment without changing external or workspace state",
                    tool=None,
                )],
            )
        return fallback

    def _fallback_plan(self, goal: str) -> AgentPlan:
        lowered = goal.lower()
        tool: str | None = None
        arguments: dict[str, Any] = {}
        explicit_url = re.search(r"https?://[^\s]+", goal, flags=re.IGNORECASE)
        common_sites = {
            "google": "https://www.google.com/",
            "github": "https://github.com/",
            "youtube": "https://www.youtube.com/",
            "gmail": "https://mail.google.com/",
        }
        if re.search(r"\b(open|launch)\b", lowered):
            url = explicit_url.group(0).rstrip(".,)") if explicit_url else next(
                (value for name, value in common_sites.items() if re.search(rf"\b{name}\b", lowered)),
                "",
            )
            if url:
                return AgentPlan(goal=goal, summary=f"Open {url} in the default browser.", steps=[
                    AgentStep(id="step-1", description=f"Open {url}", tool="open_url", arguments={"url": url}),
                ])
            app_match = re.search(r"\b(?:open|launch|start)\s+([A-Za-z0-9_.-]+)", goal, flags=re.IGNORECASE)
            if app_match:
                return AgentPlan(goal=goal, summary="Launch the requested local application.", steps=[
                    AgentStep(id="step-1", description=f"Launch {app_match.group(1)}", tool="app_launch", arguments={"app": app_match.group(1)}),
                ])
        clone_match = re.search(
            r"\bclone\b.*?((?:https://github\.com/|git@github\.com:)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?)",
            goal, flags=re.IGNORECASE,
        )
        if clone_match:
            return AgentPlan(goal=goal, summary="Clone the requested GitHub repository into the active workspace.", steps=[
                AgentStep(id="step-1", description="Clone the GitHub repository", tool="git_clone", arguments={"repository": clone_match.group(1)}),
            ])
        wants_project = bool(re.search(r"\b(create|build|make|scaffold)\b.*\b(website|site|web app|app|project)\b", lowered))
        wants_github = bool(re.search(r"\b(github|git hub|repository|repo)\b", lowered))
        wants_github_create = bool(re.search(r"\b(create|make|new|publish|push)\b.*\b(github|git hub|repository|repo)\b", lowered))
        if wants_project:
            name = self._project_name_from_goal(goal)
            kind = "website" if re.search(r"\b(website|site|web app)\b", lowered) else "python"
            steps = [
                AgentStep(id="step-1", description=f"Create the local {kind} project {name}", tool="project_create", arguments={"name": name, "kind": kind, "description": goal}),
                AgentStep(id="step-2", description="Initialize the project Git repository", tool="git_init", arguments={"path": f"projects/{name}"}),
                AgentStep(id="step-3", description="Commit the initial project files locally", tool="git_commit", arguments={"path": f"projects/{name}", "message": "Initial JARVIS project"}),
            ]
            if wants_github:
                steps.extend([
                    AgentStep(id="step-4", description="Verify the local GitHub connection", tool="github_status"),
                    AgentStep(id="step-5", description="Create the GitHub repository", tool="github_create_repo", arguments={"name": name, "visibility": "private", "path": f"projects/{name}"}),
                    AgentStep(id="step-6", description="Push the initial project to GitHub", tool="github_push", arguments={"path": f"projects/{name}"}),
                ])
            return AgentPlan(goal=goal, summary="Create a runnable local project and connect it to GitHub when requested.", steps=steps)
        if wants_github_create:
            name = self._project_name_from_goal(goal)
            return AgentPlan(goal=goal, summary="Verify GitHub access and create the requested private repository.", steps=[
                AgentStep(id="step-1", description="Verify the local GitHub connection", tool="github_status"),
                AgentStep(id="step-2", description="Create the GitHub repository", tool="github_create_repo", arguments={"name": name, "visibility": "private"}),
            ])
        if wants_github:
            return AgentPlan(goal=goal, summary="Check the local GitHub connection and report whether JARVIS can use it.", steps=[
                AgentStep(id="step-1", description="Verify the local GitHub connection", tool="github_status"),
            ])
        if re.search(r"\b(git status|git branch|current branch|working[- ]tree)\b", lowered):
            tool, arguments = "git_status", {}
        if re.search(r"\b(search|research|latest|look up|find online)\b", lowered): tool, arguments = "web_search", {"query": goal}
        elif re.search(r"\b(cpu|ram|memory|disk|system|uptime|process)\b|\b(provider|runtime|machine) health\b|\bagent runtime\b", lowered): tool, arguments = "system_info", {"action": "info"}
        elif re.search(r"\b(calculate|compute|math)\b", lowered): tool, arguments = "calculator", {"expression": goal}
        elif "nvidia" in lowered and "skill" in lowered: tool, arguments = "nvidia_skill_search", {"query": goal, "limit": 8}
        return AgentPlan(goal=goal, summary="Analyze the goal, gather relevant evidence, and synthesize a direct answer.", steps=[AgentStep(id="step-1", description="Gather the evidence needed for the goal" if tool else "Reason through the goal", tool=tool, arguments=arguments)])

    @staticmethod
    def _project_name_from_goal(goal: str) -> str:
        named = re.search(
            r"\b(?:called|named)\s+([A-Za-z0-9][A-Za-z0-9 _.\-]{0,80}?)(?=,|\s+(?:and|then|with|on|for)\b|$)",
            goal, flags=re.IGNORECASE,
        )
        if named:
            slug = re.sub(r"[^a-z0-9]+", "-", named.group(1).lower()).strip("-")
            if slug:
                return slug[:80]
        words = re.findall(r"[a-z0-9]+", goal.lower())
        ignored = {"a", "an", "the", "create", "build", "make", "scaffold", "website", "site", "web", "app", "project", "github", "repo", "repository", "for", "with", "and", "on", "called", "named", "put", "it", "initialize", "git", "commit", "verify", "files"}
        kept = [word for word in words if word not in ignored][:4]
        return "-".join(kept) or "jarvis-project"

    @staticmethod
    def _needs_execution_plan(goal: str, plan: AgentPlan) -> bool:
        wants_action = AgentRuntime.is_action_goal(goal)
        return wants_action and not any(step.tool for step in plan.steps)

    @classmethod
    def is_action_goal(cls, goal: str) -> bool:
        """Return true when a request asks Jarvis to change or operate real state."""
        normalized = goal.strip()
        consultative = re.match(
            r"^(how (?:do|can|would|should) (?:i|you)|what (?:is|are|would)|why |explain |tell me how)",
            normalized, flags=re.IGNORECASE,
        )
        return bool(cls.ACTION_PATTERN.search(normalized)) and not bool(consultative)

    @classmethod
    def should_delegate_chat_action(cls, goal: str) -> bool:
        """Route file, code, project, and repository work through the guarded runtime."""
        normalized = goal.strip()
        return bool(cls.FILE_CODE_CONTEXT_PATTERN.search(normalized)) and cls.is_action_goal(normalized)

    @classmethod
    def needs_adaptive_review(cls, goal: str) -> bool:
        return bool(cls.ADAPTIVE_PATTERN.search(goal)) and cls.is_action_goal(goal)

    async def _continue_plan(self, run: AgentRun) -> list[AgentStep]:
        """Review observations and choose the next concrete action, if any."""
        evidence = json.dumps(run.observations[-6:], ensure_ascii=False, indent=2)
        valid_tools = (
            set(self.TOOL_DESCRIPTIONS)
            if run.allowed_tools is None
            else set(run.allowed_tools)
        )
        tools = "\n".join(
            f"- {name}: {description}"
            for name, description in self.TOOL_DESCRIPTIONS.items()
            if name in valid_tools
        ) or "- No tools are authorized."
        prompt = f"""You are the observe-act-repair controller for JARVIS.
Goal: {run.goal}
Workspace: {run.workspace_root}
Completed steps: {run.current_step}/{run.max_steps}
Recent observations:
{evidence}

Decide whether the requested real-world result is verified. If it is not verified, return one
or two concrete next tool steps. Prefer inspection after an error and a test/status command after
a write. Never repeat an identical failed action. Never claim completion without tool evidence.

Available tools:
{tools}

Return JSON only:
{{"done":true|false,"summary":"brief status","next_steps":[{{"id":"step-N","description":"...","tool":"tool_name","arguments":{{}},"expected_output":"..."}}]}}
"""
        client = await self.jarvis._require_provider_client()
        response = await client.chat_completion(
            [
                {"role": "system", "content": "Return strict JSON for an autonomous tool controller."},
                {"role": "user", "content": prompt},
            ],
            model=run.model, temperature=0.1, max_tokens=900,
        )
        raw = response["choices"][0]["message"]["content"]
        payload = self._parse_json(raw)
        if payload.get("done", False):
            return []
        steps: list[AgentStep] = []
        for index, item in enumerate(payload.get("next_steps") or []):
            if len(steps) >= 2:
                break
            candidate = dict(item)
            candidate["id"] = f"step-{run.current_step + index + 1}"
            step = AgentStep.model_validate(candidate)
            if step.tool not in valid_tools:
                continue
            steps.append(step)
        return steps

    async def _execute(self, run: AgentRun) -> None:
        if not run.plan or run.status == "cancelled":
            return
        if not self._effect_allowed(run, "run_launch"):
            return
        run.status = "running"
        while run.current_step < len(run.plan.steps):
            step = run.plan.steps[run.current_step]
            self._require_tool_allowed(run, step.tool)
            self._resolve_step_context(run, step)
            if self._requires_confirmation(run, step) and step.id not in run.approved_steps:
                run.status = "awaiting_confirmation"; run.updated_at = datetime.now().isoformat()
                self._event(run, "approval", "required", f"Confirmation required: {step.description}", {"step": step.model_dump()})
                return
            if not self._effect_allowed(run, "tool" if step.tool else "provider"):
                return
            self._event(run, "tool", "start", step.description, {"step_id": step.id, "tool": step.tool})
            started = time.monotonic()
            try:
                result = await self._with_retry(
                    run, f"tool:{step.tool or 'reasoning'}",
                    lambda: self._execute_tool(step.tool, step.arguments, run.workspace_root),
                ) if step.tool else "No tool required; use model reasoning during synthesis."
                safe_result = self._sanitize_evidence(result)
                observation = {
                    "step_id": step.id,
                    "tool": step.tool,
                    "result": self._evidence_text(safe_result, limit=12000),
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "ok": True,
                }
                if isinstance(safe_result, (dict, list, str, int, float, bool)) or safe_result is None:
                    observation["data"] = safe_result
            except Exception as exc:
                observation = {"step_id": step.id, "tool": step.tool, "code": self._safe_error_code(exc), "duration_ms": round((time.monotonic() - started) * 1000), "ok": False}
            if not self._effect_allowed(run, "result_persistence"):
                return
            run.observations.append(observation); run.current_step += 1
            self._event(run, "tool", "end" if observation["ok"] else "error", f"{'Completed' if observation['ok'] else 'Failed'} {step.id}", observation)
            if run.current_step >= len(run.plan.steps) and run.current_step < run.max_steps and self.needs_adaptive_review(run.goal):
                try:
                    next_steps = await self._with_retry(
                        run, "review", lambda: self._continue_plan(run),
                    )
                except Exception as exc:
                    next_steps = []
                    self._event(run, "review", "warning", "Adaptive review was unavailable", {"code": self._safe_error_code(exc)})
                if next_steps:
                    run.plan.steps.extend(next_steps[: run.max_steps - len(run.plan.steps)])
                    self._event(run, "planning", "extended", "Added follow-up steps after observing real tool output", {"steps": len(next_steps)})
            if not observation["ok"] and run.current_step >= len(run.plan.steps):
                raise RuntimeError("tool_step_failed")
        run.status = "synthesizing"
        self._event(run, "synthesis", "start", "Synthesizing the final answer from verified observations")
        successful_tools = {
            item.get("tool") for item in run.observations
            if item.get("ok") and item.get("tool")
        }
        has_successful_write = any(
            item.get("ok") and item.get("tool") in self.WRITE_TOOLS
            for item in run.observations
        )
        content_reads = successful_tools.intersection(self.CONTENT_READ_TOOLS)
        if has_successful_write or (
            successful_tools and successful_tools.issubset(self.STATUS_RECEIPT_TOOLS)
        ):
            run.result = self._execution_receipt(run)
        elif content_reads:
            if not self._effect_allowed(run, "provider"):
                return
            try:
                run.result = await self._with_retry(run, "synthesis", lambda: self._synthesize(run))
            except Exception as exc:
                self._event(
                    run,
                    "synthesis",
                    "warning",
                    "Provider synthesis was unavailable; returning verified tool evidence",
                    {"code": self._safe_error_code(exc)},
                )
                run.result = self._execution_receipt(run)
        else:
            if not self._effect_allowed(run, "provider"):
                return
            run.result = await self._with_retry(run, "synthesis", lambda: self._synthesize(run))
        if not self._effect_allowed(run, "result_persistence"):
            return
        run.status = "completed"; run.updated_at = datetime.now().isoformat()
        self._event(run, "run", "completed", "Agent run completed", {"model": run.model})
        if run.record_conversation:
            self.jarvis.conversation_history.extend([
                {"role": "user", "content": run.goal, "timestamp": run.created_at},
                {"role": "assistant", "content": run.result, "timestamp": run.updated_at, "agent_run_id": run.id},
            ])
            if self.jarvis.memory:
                asyncio.create_task(self.jarvis._save_conversation(run.goal, run.result))

    @classmethod
    def _redact_text(cls, value: str) -> str:
        """Remove common credential forms before evidence is persisted or synthesized."""
        redacted = re.sub(r"\bnvapi-[A-Za-z0-9_-]{12,}\b", "nvapi-[REDACTED]", value, flags=re.IGNORECASE)
        redacted = re.sub(
            r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b",
            "[REDACTED_CREDENTIAL]",
            redacted,
            flags=re.IGNORECASE,
        )
        redacted = re.sub(
            r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/-]{12,}=*",
            r"\1[REDACTED]",
            redacted,
        )
        assignment = re.compile(
            r"(?im)\b([A-Z0-9_.-]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|REFRESH[_-]?TOKEN|PASSWORD|PASSWD|SECRET|CREDENTIAL)"
            r"[A-Z0-9_.-]*\s*[:=]\s*)([^\s,;]+)"
        )
        return assignment.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)

    @classmethod
    def _sanitize_evidence(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): (
                    "[REDACTED]"
                    if cls.SENSITIVE_FIELD_PATTERN.fullmatch(str(key))
                    else cls._sanitize_evidence(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._sanitize_evidence(item) for item in value]
        if isinstance(value, tuple):
            return [cls._sanitize_evidence(item) for item in value]
        if isinstance(value, str):
            return cls._redact_text(value)
        return value

    @classmethod
    def _evidence_text(cls, value: Any, *, limit: int, compact: bool = False) -> str:
        sanitized = cls._sanitize_evidence(value)
        if isinstance(sanitized, str):
            rendered = sanitized
        else:
            rendered = json.dumps(sanitized, ensure_ascii=False, default=str)
        rendered = cls._redact_text(rendered)
        if compact:
            rendered = re.sub(r"\s+", " ", rendered).strip()
        return rendered[:limit]

    def _execution_receipt(self, run: AgentRun) -> str:
        completed = [item for item in run.observations if item.get("ok")]
        failed = [item for item in run.observations if not item.get("ok")]
        tools = [str(item.get("tool")) for item in completed if item.get("tool")]
        lines = [
            f"Completed: {run.goal}",
            f"Executed {len(completed)} verified tool step{'s' if len(completed) != 1 else ''}: "
            f"{', '.join(tools) or 'reasoning'}.",
        ]
        for item in completed:
            tool = item.get("tool")
            data = item.get("data", item.get("result", ""))
            handled = False
            if isinstance(data, dict):
                if tool == "project_create" and data.get("path"):
                    lines.append(f"Project created at {data['path']}.")
                    handled = True
                elif tool in {"workspace_write", "workspace_patch", "directory_create"} and data.get("path"):
                    lines.append(f"Updated {data['path']}.")
                    handled = True
                elif tool == "git_commit":
                    nested = data.get("result") if isinstance(data.get("result"), dict) else {}
                    stdout = str(data.get("stdout") or nested.get("stdout", "")).strip()
                    if stdout:
                        lines.append(f"Git commit: {stdout.splitlines()[-1][:240]}")
                    handled = True
                elif tool == "github_status":
                    state = "authenticated" if data.get("authenticated") else "not authenticated"
                    lines.append(f"GitHub CLI is {state}.")
                    handled = True
                elif tool == "git_status":
                    status = data.get("status") if isinstance(data.get("status"), dict) else {}
                    output = str(status.get("stdout", "")).strip().splitlines()
                    if output:
                        lines.append(f"Git status: {output[0][:300]}")
                        lines.append(f"Working tree entries: {max(0, len(output) - 1)} changed or untracked paths.")
                    handled = True
                elif tool == "system_info":
                    lines.append(f"System evidence: {self._evidence_text(data, limit=1200, compact=True)}")
                    handled = True
                elif tool == "github_create_repo":
                    lines.append(f"GitHub repository {data.get('repository', '')} created ({data.get('visibility', 'private')}).")
                    handled = True
                elif tool == "github_push" and data.get("exit_code") == 0:
                    lines.append("GitHub push completed successfully.")
                    handled = True
            if not handled and tool in self.CONTENT_READ_TOOLS:
                evidence = self._evidence_text(data, limit=2400, compact=True)
                lines.append(f"{tool} evidence: {evidence or '[no content returned]'}")
        if failed:
            lines.append(f"Recovered from {len(failed)} failed attempt{'s' if len(failed) != 1 else ''}; see Agent Trace for details.")
        lines.append(f"Workspace: {run.workspace_root}")
        return "\n".join(lines)

    def _resolve_step_context(self, run: AgentRun, step: AgentStep) -> None:
        """Carry concrete paths returned by earlier tools into later plan steps."""
        created_path = ""
        for observation in reversed(run.observations):
            if observation.get("tool") == "project_create" and observation.get("ok"):
                data = observation.get("data")
                if isinstance(data, dict):
                    created_path = str(data.get("path", "")).strip()
                if created_path:
                    break
        if not created_path:
            return
        path_tools = {
            "workspace_list", "workspace_read", "workspace_search", "git_status",
            "git_init", "git_commit", "github_create_repo", "github_push",
            "github_pr_create", "open_path", "command_run",
        }
        if step.tool not in path_tools:
            return
        raw_path = str(step.arguments.get("path", "")).strip()
        active_root = self._resolve_workspace_root(run.workspace_root)
        if not raw_path or not (active_root / raw_path).resolve().exists():
            step.arguments["path"] = created_path

    def _requires_confirmation(self, run: AgentRun, step: AgentStep) -> bool:
        if step.tool not in self.WRITE_TOOLS:
            return False
        if step.tool in self.LOCAL_EXECUTION_TOOLS:
            return True
        if step.tool in self.REMOTE_WRITE_TOOLS:
            if run.autonomy != "full":
                return True
            # Full Auto is still scoped to the user's explicit instruction. A planner
            # cannot invent a GitHub side effect that Ahmed did not ask for.
            remote_request = bool(re.search(
                r"\b(github|repo|repository|issue|pull request|pr|push|publish)\b",
                run.goal, flags=re.IGNORECASE,
            ))
            return not remote_request
        if run.autonomy != "full":
            return True
        # Full Auto can mutate only its configured local workspace and local Jarvis data.
        # Local process execution was handled above and never bypasses confirmation.
        return False

    async def _execute_tool(
        self, tool: str | None, arguments: dict[str, Any],
        workspace_root: str | Path | None = None,
    ) -> Any:
        active_root = self._resolve_workspace_root(workspace_root)
        if tool == "system_info":
            action = str(arguments.get("action", "info"))
            if action not in {"info", "cpu", "memory", "disk", "processes", "uptime", "network"}: action = "info"
            return await self.jarvis.execute_skill("system", {"action": action})
        if tool == "web_search": return await self.jarvis.execute_skill("web_search", {"query": str(arguments.get("query", ""))})
        if tool == "calculator": return await self.jarvis.execute_skill("calculator", {"expression": str(arguments.get("expression", ""))})
        if tool == "memory_search": return await self.jarvis.recall(str(arguments.get("query", "")), min(10, max(1, int(arguments.get("limit", 5)))))
        if tool == "nvidia_skill_search": return [item.to_dict() for item in self.nvidia_skills.search(str(arguments.get("query", "")), limit=min(20, max(1, int(arguments.get("limit", 8)))))]
        if tool == "notes_search": return await self.jarvis.execute_skill("note", {"action": "search", "query": str(arguments.get("query", ""))})
        if tool == "calendar_list": return await self.jarvis.execute_skill("calendar", {"action": "list", "day": str(arguments.get("day", ""))})
        if tool == "reminders_list": return await self.jarvis.execute_skill("reminder", {"action": "list"})
        if tool == "note_create": return await self.jarvis.execute_skill("note", {"action": "create", "title": str(arguments.get("title", "Agent note")), "content": str(arguments.get("content", ""))})
        if tool == "reminder_set": return await self.jarvis.execute_skill("reminder", {"action": "set", "text": str(arguments.get("text", "")), "when": str(arguments.get("when", ""))})
        if tool == "calendar_create": return await self.jarvis.execute_skill("calendar", {"action": "create_event", **arguments})
        if tool == "workspace_list":
            path = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", root=active_root)
            items = []
            for item in sorted(path.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower()))[:300]:
                items.append({"name": item.name, "path": str(item.relative_to(active_root)), "type": "directory" if item.is_dir() else "file", "size": item.stat().st_size if item.is_file() else None})
            return {"root": str(active_root), "path": str(path), "items": items}
        if tool == "workspace_read":
            path = self._workspace_path(str(arguments.get("path", "")), must_exist=True, root=active_root)
            if not path.is_file():
                raise ValueError("workspace_read requires a file")
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            start = max(1, int(arguments.get("start_line", 1)))
            end = min(len(lines), int(arguments.get("end_line", start + 399)))
            return {"path": str(path.relative_to(active_root)), "start_line": start, "end_line": end, "content": "\n".join(lines[start - 1:end])[:40000]}
        if tool == "workspace_search":
            query = str(arguments.get("query", "")).strip()
            if not query:
                raise ValueError("workspace_search requires query")
            search_path = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            glob = str(arguments.get("glob", "")).strip()
            if shutil.which("rg"):
                command = ["rg", "--line-number", "--no-heading", "--color", "never"]
                if glob:
                    command.extend(["--glob", glob])
                command.extend(["--", query, str(search_path)])
                return await self._run_process(
                    command, timeout=30, cwd=active_root, allowed_exit_codes={0, 1}
                )
            return self._search_workspace_python(search_path, query, glob, active_root)
        if tool == "git_status":
            root = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            status = await self._run_process(["git", "status", "--short", "--branch"], timeout=20, cwd=root)
            diff = await self._run_process(["git", "diff", "--stat"], timeout=20, cwd=root)
            return {"path": str(root.relative_to(active_root)), "status": status, "diff_stat": diff}
        if tool == "workspace_write":
            path = self._workspace_path(str(arguments.get("path", "")), root=active_root)
            content = str(arguments.get("content", ""))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"path": str(path.relative_to(active_root)), "written_chars": len(content)}
        if tool == "workspace_patch":
            path = self._workspace_path(str(arguments.get("path", "")), must_exist=True, root=active_root)
            old_text, new_text = str(arguments.get("old_text", "")), str(arguments.get("new_text", ""))
            if not old_text:
                raise ValueError("workspace_patch requires non-empty old_text")
            content = path.read_text(encoding="utf-8")
            matches = content.count(old_text)
            if matches != 1:
                raise ValueError(f"workspace_patch expected exactly one match, found {matches}")
            path.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
            return {"path": str(path.relative_to(active_root)), "replacements": 1}
        if tool == "directory_create":
            path = self._workspace_path(str(arguments.get("path", "")).strip(), root=active_root)
            path.mkdir(parents=True, exist_ok=True)
            return {"path": str(path.relative_to(active_root)), "created": True}
        if tool == "command_run":
            command = str(arguments.get("command", "")).strip()
            self._validate_command(command)
            timeout = max(1, min(int(arguments.get("timeout_seconds", 60)), 120))
            root = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            executable = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command] if os.name == "nt" else ["bash", "-lc", command]
            return await self._run_process(executable, timeout=timeout, scrub_secrets=True, cwd=root)
        if tool == "project_create":
            return self._create_project(active_root, arguments)
        if tool == "git_clone":
            repository = str(arguments.get("repository", "")).strip()
            if not re.fullmatch(r"(?:https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?|git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?)", repository):
                raise ValueError("git_clone currently accepts an explicit GitHub HTTPS or SSH repository URL")
            directory = str(arguments.get("directory", "")).strip()
            command = ["git", "clone", "--", repository]
            if directory:
                target = self._workspace_path(directory, root=active_root)
                if target.exists():
                    raise FileExistsError(str(target))
                command.append(str(target))
            return await self._run_process(command, timeout=120, cwd=active_root)
        if tool == "git_init":
            root = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            if not root.is_dir():
                raise ValueError("git_init path must be a directory")
            result = await self._run_process(["git", "init"], timeout=30, cwd=root)
            return {"path": str(root.relative_to(active_root)), **result}
        if tool == "git_commit":
            root = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            message = str(arguments.get("message", "JARVIS update")).strip()
            if not message:
                raise ValueError("git_commit requires a commit message")
            await self._run_process(["git", "add", "--all"], timeout=30, cwd=root)
            result = await self._run_process(["git", "-c", "user.name=JARVIS", "-c", "user.email=jarvis@localhost", "commit", "-m", message], timeout=45, cwd=root)
            return {"path": str(root.relative_to(active_root)), **result}
        if tool == "github_status":
            if not shutil.which("gh"):
                return {"available": False, "authenticated": False, "detail": "GitHub CLI (gh) is not installed"}
            result = await self._run_process(
                ["gh", "auth", "status"],
                timeout=30,
                cwd=active_root,
                allowed_exit_codes={0, 1},
            )
            return {"available": True, "authenticated": result["exit_code"] == 0, **result}
        if tool == "github_repo_view":
            if not shutil.which("gh"):
                raise RuntimeError("GitHub CLI (gh) is not installed")
            repository = str(arguments.get("repository", "")).strip()
            command = ["gh", "repo", "view"]
            if repository:
                if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
                    raise ValueError("repository must use owner/name format")
                command.append(repository)
            command.extend(["--json", "nameWithOwner,url,visibility,defaultBranchRef,description"])
            return await self._run_process(command, timeout=30, cwd=active_root)
        if tool == "github_create_repo":
            root = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            name = str(arguments.get("name", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name):
                raise ValueError("GitHub repository name must be 1-100 letters, numbers, dots, underscores, or hyphens")
            visibility = str(arguments.get("visibility", "private")).lower()
            if visibility not in {"private", "public"}:
                raise ValueError("GitHub visibility must be private or public")
            if not shutil.which("gh"):
                raise RuntimeError("GitHub CLI (gh) is not installed")
            result = await self._run_process(["gh", "repo", "create", name, f"--{visibility}", "--source=.", "--remote=origin"], timeout=90, cwd=root)
            return {"path": str(root.relative_to(active_root)), "repository": name, "visibility": visibility, **result}
        if tool == "github_push":
            root = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            result = await self._run_process(["git", "push", "-u", "origin", "HEAD"], timeout=120, cwd=root)
            return {"path": str(root.relative_to(active_root)), **result}
        if tool == "github_issue_create":
            if not shutil.which("gh"):
                raise RuntimeError("GitHub CLI (gh) is not installed")
            title, body = str(arguments.get("title", "")).strip(), str(arguments.get("body", "")).strip()
            if not title:
                raise ValueError("github_issue_create requires title")
            command = ["gh", "issue", "create", "--title", title, "--body", body or "Created by JARVIS"]
            repository = str(arguments.get("repository", "")).strip()
            if repository:
                if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
                    raise ValueError("repository must use owner/name format")
                command.extend(["--repo", repository])
            return await self._run_process(command, timeout=60, cwd=active_root)
        if tool == "github_pr_create":
            if not shutil.which("gh"):
                raise RuntimeError("GitHub CLI (gh) is not installed")
            root = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            title, body = str(arguments.get("title", "")).strip(), str(arguments.get("body", "")).strip()
            if not title:
                raise ValueError("github_pr_create requires title")
            command = ["gh", "pr", "create", "--title", title, "--body", body or "Created by JARVIS"]
            base = str(arguments.get("base", "")).strip()
            if base:
                command.extend(["--base", base])
            return await self._run_process(command, timeout=90, cwd=root)
        if tool == "open_url":
            url = str(arguments.get("url", "")).strip()
            if not re.fullmatch(r"https?://[^\s]+", url, flags=re.IGNORECASE):
                raise ValueError("open_url requires an http or https URL")
            if os.name == "nt":
                os.startfile(url)  # type: ignore[attr-defined]
            else:
                await self._run_process(["xdg-open", url], timeout=15, cwd=active_root)
            return {"url": url, "opened": True}
        if tool == "open_path":
            path = self._workspace_path(str(arguments.get("path", ".")).strip() or ".", must_exist=True, root=active_root)
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                await self._run_process(["xdg-open", str(path)], timeout=15, cwd=active_root)
            return {"path": str(path.relative_to(active_root)), "opened": True}
        if tool == "app_launch":
            app = str(arguments.get("app", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}(?:\.exe)?", app):
                raise ValueError("app_launch requires a simple executable name")
            normalized_app = app.casefold()
            if normalized_app.endswith(".exe"):
                normalized_app = normalized_app[:-4]
            if normalized_app in self.BLOCKED_APP_LAUNCHERS:
                raise PermissionError("app_launch blocks shell, script-host, and proxy executables")
            raw_args = arguments.get("arguments", [])
            app_args = [str(value) for value in raw_args[:20]] if isinstance(raw_args, list) else []
            process = await asyncio.create_subprocess_exec(app, *app_args, cwd=str(active_root))
            return {"app": app, "pid": process.pid, "launched": True}
        return "No tool was selected."

    def _create_project(self, root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
        name = str(arguments.get("name", "")).strip()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug or len(slug) > 80:
            raise ValueError("Project name must produce a 1-80 character folder name")
        kind = str(arguments.get("kind", "website")).lower()
        if kind not in {"website", "python"}:
            raise ValueError("Project kind must be website or python")
        relative = str(arguments.get("directory", f"projects/{slug}")).strip() or f"projects/{slug}"
        project = self._workspace_path(relative, root=root)
        if project.exists():
            raise FileExistsError(f"Project folder already exists: {project.relative_to(root)}")
        description = str(arguments.get("description", "Created by JARVIS.")).strip()[:500] or "Created by JARVIS."
        project.mkdir(parents=True)
        files: dict[str, str]
        if kind == "website":
            files = {
                "index.html": f"""<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{name}</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><main><p class=\"eyebrow\">BUILT BY JARVIS</p><h1>{name}</h1><p>{description}</p><button id=\"action\">Get started</button></main><script src=\"app.js\"></script></body></html>\n""",
                "styles.css": "body{margin:0;min-height:100vh;display:grid;place-items:center;background:#061019;color:#e9fbff;font-family:system-ui,sans-serif}main{max-width:640px;padding:48px;border:1px solid #16d9ff;background:#091b26;box-shadow:0 0 50px #00d5ff22}h1{font-size:clamp(2.5rem,8vw,5rem);margin:.1em 0}.eyebrow{color:#42e8ff;letter-spacing:.18em;font-size:.72rem}button{padding:.8rem 1.1rem;background:#42e8ff;color:#041016;border:0;font-weight:700;cursor:pointer}\n",
                "app.js": "document.querySelector('#action').addEventListener('click',()=>alert('Your JARVIS project is ready.'));\n",
                "README.md": f"# {name}\n\n{description}\n\nOpen `index.html` in a browser to run the starter site.\n",
            }
        else:
            files = {
                "main.py": f"\"\"\"{name}.\"\"\"\n\ndef main() -> None:\n    print(\"{name} is ready.\")\n\n\nif __name__ == \"__main__\":\n    main()\n",
                "README.md": f"# {name}\n\n{description}\n\nRun with `python main.py`.\n",
                ".gitignore": "__pycache__/\n.venv/\n",
            }
        files[".gitignore"] = files.get(".gitignore", "node_modules/\ndist/\n.env\n")
        for relative_path, content in files.items():
            (project / relative_path).write_text(content, encoding="utf-8")
        return {"path": str(project.relative_to(root)), "kind": kind, "files": sorted(files), "created": True}

    @staticmethod
    def _search_workspace_python(search_path: Path, query: str, glob: str, root: Path) -> dict[str, Any]:
        """Portable text search used when ripgrep is absent from the service PATH."""
        try:
            pattern = re.compile(query)
        except re.error:
            pattern = re.compile(re.escape(query))
        ignored = {".git", "node_modules", "dist", "build", ".venv", "__pycache__"}
        matches: list[str] = []
        files = [search_path] if search_path.is_file() else search_path.rglob("*")
        for path in files:
            if len(matches) >= 500 or not path.is_file() or any(part in ignored for part in path.parts):
                continue
            relative = path.relative_to(root)
            if glob and not (relative.match(glob) or path.match(glob)):
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if pattern.search(line):
                        matches.append(f"{relative}:{number}:{line[:500]}")
                        if len(matches) >= 500:
                            break
            except OSError:
                continue
        return {"exit_code": 0 if matches else 1, "stdout": "\n".join(matches), "stderr": "", "fallback": "python"}

    def _resolve_workspace_root(self, root: str | Path | None) -> Path:
        candidate = Path(root).expanduser().resolve() if root else self.workspace_root
        if not candidate.exists() or not candidate.is_dir():
            raise ValueError(f"Workspace root is not an existing directory: {candidate}")
        return candidate

    def _workspace_path(
        self, relative: str, must_exist: bool = False, root: str | Path | None = None,
    ) -> Path:
        if not relative.strip():
            raise ValueError("A workspace-relative path is required")
        workspace_root = self._resolve_workspace_root(root)
        candidate = (workspace_root / relative).resolve()
        try:
            candidate.relative_to(workspace_root)
        except ValueError as exc:
            raise PermissionError("Path escapes the configured JARVIS workspace") from exc
        if must_exist and not candidate.exists():
            raise FileNotFoundError(str(candidate))
        return candidate

    @staticmethod
    def _validate_command(command: str) -> None:
        if not command:
            raise ValueError("command_run requires command")
        blocked = [
            r"\b(remove-item|del|erase|rmdir|rd)\b.*\b(recurse|/s|/q)\b",
            r"\b(format|diskpart|shutdown|restart-computer|stop-computer)\b",
            r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|push\s+.*--force)\b",
            r"\b(reg\s+delete|bcdedit|cipher\s+/w)\b",
        ]
        for pattern in blocked:
            if re.search(pattern, command, flags=re.IGNORECASE):
                raise PermissionError("Command blocked by the autonomous safety policy")

    async def _run_process(
        self, command: list[str], timeout: int, scrub_secrets: bool = False,
        cwd: str | Path | None = None,
        allowed_exit_codes: set[int] | frozenset[int] | None = None,
    ) -> dict[str, Any]:
        environment = os.environ.copy()
        if scrub_secrets:
            for key in list(environment):
                if any(token in key.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                    environment.pop(key, None)
        process = await asyncio.create_subprocess_exec(
            *command, cwd=str(self._resolve_workspace_root(cwd)), env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise TimeoutError(f"Command exceeded {timeout} seconds")
        result = {
            "exit_code": process.returncode,
            "stdout": stdout.decode(errors="replace")[-30000:],
            "stderr": stderr.decode(errors="replace")[-15000:],
        }
        allowed = frozenset({0} if allowed_exit_codes is None else allowed_exit_codes)
        if process.returncode not in allowed:
            raise ToolProcessError(process.returncode)
        return result

    async def _synthesize(self, run: AgentRun) -> str:
        evidence = json.dumps(run.observations, ensure_ascii=False, indent=2)
        messages = [
            {"role": "system", "content": self.jarvis.system_prompt + "\nYou are completing an agent run. Base claims on tool observations. State limitations clearly. Do not mention hidden reasoning."},
            {"role": "user", "content": f"Goal:\n{run.goal}\n\nPlan summary:\n{run.plan.summary if run.plan else ''}\n\nTool observations:\n{evidence}\n\nGive Ahmed the completed result and concise next actions."},
        ]
        client = await self.jarvis._require_provider_client()
        response = await client.chat_completion(
            messages, model=run.model, temperature=0.25, max_tokens=1800
        )
        return response["choices"][0]["message"]["content"]

    def create_schedule(
        self, goal: str, next_run_at: str, interval_seconds: int | None = None,
        model: str = "auto", max_steps: int = 8, autonomy: str = "guarded",
    ) -> dict[str, Any]:
        run_at = self._parse_schedule_time(next_run_at)
        if interval_seconds is not None and interval_seconds < 60:
            raise ValueError("Recurring schedules must be at least 60 seconds apart")
        now = datetime.now().isoformat()
        schedule = {
            "id": f"schedule-{uuid.uuid4().hex[:12]}", "goal": goal,
            "next_run_at": run_at.isoformat(), "interval_seconds": interval_seconds,
            "model": model, "max_steps": max(1, min(max_steps, 12)),
            "autonomy": "full" if autonomy == "full" else "guarded",
            "enabled": True, "created_at": now, "updated_at": now, "last_run_id": None,
        }
        self.schedules[schedule["id"]] = schedule
        self.store.save_schedule(schedule)
        return schedule

    def list_schedules(self) -> list[dict[str, Any]]:
        return sorted(self.schedules.values(), key=lambda item: item["next_run_at"])

    def delete_schedule(self, schedule_id: str) -> None:
        if schedule_id not in self.schedules:
            raise KeyError(schedule_id)
        self.schedules.pop(schedule_id)
        self.store.delete_schedule(schedule_id)

    async def _scheduler_loop(self) -> None:
        while self._started:
            now = datetime.now()
            for schedule in list(self.schedules.values()):
                if not schedule.get("enabled", True):
                    continue
                try:
                    due = self._parse_schedule_time(schedule["next_run_at"])
                except ValueError:
                    schedule["enabled"] = False
                    self.store.save_schedule(schedule)
                    continue
                if due > now:
                    continue
                run = await self.submit(
                    schedule["goal"], schedule.get("model", "auto"), schedule.get("max_steps", 8),
                    schedule.get("autonomy", "guarded"),
                )
                run.schedule_id = schedule["id"]
                self._persist(run)
                schedule["last_run_id"] = run.id
                interval = schedule.get("interval_seconds")
                if interval:
                    while due <= now:
                        due += timedelta(seconds=int(interval))
                    schedule["next_run_at"] = due.isoformat()
                    schedule["updated_at"] = datetime.now().isoformat()
                else:
                    schedule["enabled"] = False
                self.store.save_schedule(schedule)
            await asyncio.sleep(2)

    @staticmethod
    def _parse_schedule_time(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise json.JSONDecodeError("No JSON object", cleaned, 0)
        return json.loads(cleaned[start:end + 1])

    def _event(self, run: AgentRun, stage: str, event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        run.events.append({"timestamp": datetime.now().isoformat(), "stage": stage, "event_type": event_type, "message": message, "data": data or {}})
        run.updated_at = datetime.now().isoformat()
        self._persist(run)

    def _persist(self, run: AgentRun) -> None:
        payload = run.to_dict()
        payload["approved_steps"] = sorted(run.approved_steps)
        self.store.save_run(payload)

    def _require_global_effect(self, boundary: str) -> None:
        if self.stop_guard is not None:
            self.stop_guard.require_effect_allowed(boundary=boundary)

    def _effect_allowed(self, run: AgentRun, boundary: str) -> bool:
        if self.control_service is None:
            return True
        try:
            StopGuard(self.control_service, run_id=run.id).require_effect_allowed(
                boundary=boundary
            )
            return True
        except ControlBlockedError as exc:
            snapshot = exc.snapshot
            run.status = (
                "paused"
                if snapshot is not None and snapshot.state is ControlState.PAUSED
                else "stopping"
            )
            run.error = "control_blocked"
            self._event(
                run,
                "control",
                "blocked",
                "Durable control state blocked a new effect",
                {
                    "code": "control_blocked",
                    "boundary": boundary,
                    "revision": None if snapshot is None else snapshot.revision,
                },
            )
            return False

    @staticmethod
    def _safe_error_code(exc: BaseException) -> str:
        if isinstance(exc, ControlBlockedError):
            return "control_blocked"
        if isinstance(exc, ProviderSafeError):
            return exc.code
        if isinstance(exc, ToolProcessError):
            return f"tool_exit_{exc.exit_code}"
        name = type(exc).__name__.removesuffix("Error") or "runtime"
        normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", name).casefold()
        return f"{normalized}_error"[:128]

    def _prune_runs(self) -> None:
        if len(self.runs) <= 100:
            return
        for run_id in list(self.runs)[:-100]:
            self.runs.pop(run_id, None)
