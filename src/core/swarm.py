"""Persistent, dependency-aware multi-agent orchestration for JARVIS."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from src.clients.nvidia_client import NVIDIAClient
from src.config import config
from src.core.control import ControlBlockedError, ControlService, ControlState, StopGuard
from src.core.swarm_store import SwarmStore
from src.core.workspaces import WorkspaceRegistry

if TYPE_CHECKING:
    from src.core.jarvis import Jarvis

logger = logging.getLogger(__name__)


SPECIALIST_PROFILES: dict[str, str] = {
    "manager": "Decompose goals, coordinate specialists, track dependencies, and deliver a coherent outcome.",
    "coder": "Implement and refactor software with focused, minimal, testable changes.",
    "researcher": "Gather authoritative evidence, compare alternatives, and clearly cite limitations.",
    "designer": "Design usable interfaces, interaction flows, accessibility, and polished visual systems.",
    "tester": "Create and run proportionate tests; reproduce failures and report evidence.",
    "reviewer": "Independently review correctness, security, maintainability, and unmet requirements.",
    "devops": "Handle builds, processes, deployment, reliability, observability, and recovery.",
    "judge": "Compare independent work, resolve disagreements by evidence, and synthesize the final decision.",
}
WRITER_ROLES = {"coder", "designer", "devops"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class PlannedTask(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1600)
    role: str
    dependencies: list[str] = Field(default_factory=list)
    writer: bool = False


class SwarmPlan(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)
    tasks: list[PlannedTask] = Field(min_length=1, max_length=32)


@dataclass
class SwarmTask:
    id: str
    swarm_id: str
    title: str
    objective: str
    role: str
    dependencies: list[str] = field(default_factory=list)
    writer: bool = False
    status: str = "queued"
    model: str = "auto"
    agent_run_id: str | None = None
    result: str = ""
    error: str = ""
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return vars(self).copy()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SwarmTask":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in payload.items() if key in allowed})


@dataclass
class SwarmRun:
    id: str
    goal: str
    mode: str
    project_id: str
    project_root: str = ""
    base_root: str = ""
    workspace_mode: str = "direct"
    worktree_id: str = ""
    worktree_branch: str = ""
    integration_status: str = "not_applicable"
    integration_error: str = ""
    changes: dict[str, Any] = field(default_factory=dict)
    autonomy: str = "guarded"
    requested_model: str = "auto"
    max_agents: int = 8
    max_runtime_seconds: int = 1800
    deadline_at: str = ""
    status: str = "planning"
    plan_summary: str = ""
    result: str = ""
    error: str = ""
    tasks: dict[str, SwarmTask] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self, include_tasks: bool = True) -> dict[str, Any]:
        payload = {
            "id": self.id, "goal": self.goal, "mode": self.mode,
            "project_id": self.project_id, "project_root": self.project_root,
            "base_root": self.base_root, "workspace_mode": self.workspace_mode,
            "worktree_id": self.worktree_id, "worktree_branch": self.worktree_branch,
            "integration_status": self.integration_status,
            "integration_error": self.integration_error, "changes": self.changes,
            "autonomy": self.autonomy,
            "requested_model": self.requested_model, "max_agents": self.max_agents,
            "max_runtime_seconds": self.max_runtime_seconds, "deadline_at": self.deadline_at,
            "status": self.status,
            "plan_summary": self.plan_summary, "result": self.result,
            "error": self.error, "events": self.events,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        if include_tasks:
            payload["tasks"] = [task.to_dict() for task in self.tasks.values()]
            payload["agents"] = [
                {
                    "id": role, "name": "JARVIS MANAGER" if role == "manager" else role.replace("_", " ").upper(), "role": role,
                    "model": next((task.model for task in self.tasks.values() if task.role == role), "auto"),
                    "status": next((task.status for task in self.tasks.values() if task.role == role and task.status == "running"),
                                   next((task.status for task in self.tasks.values() if task.role == role), "idle")),
                    "task": next((task.title for task in self.tasks.values() if task.role == role and task.status == "running"),
                                 next((task.title for task in self.tasks.values() if task.role == role), "Awaiting assignment")),
                }
                for role in SPECIALIST_PROFILES
            ]
            payload["results"] = [
                {"id": task.id, "title": task.title, "summary": task.result, "role": task.role}
                for task in self.tasks.values() if task.status == "completed" and task.result
            ]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SwarmRun":
        tasks = {
            item["id"]: SwarmTask.from_dict(item)
            for item in payload.get("tasks", [])
        }
        return cls(
            id=payload["id"], goal=payload["goal"], mode=payload.get("mode", "cowork"),
            project_id=payload.get("project_id", "default"),
            project_root=payload.get("project_root", ""),
            base_root=payload.get("base_root", payload.get("project_root", "")),
            workspace_mode=payload.get("workspace_mode", "direct"),
            worktree_id=payload.get("worktree_id", ""),
            worktree_branch=payload.get("worktree_branch", ""),
            integration_status=payload.get("integration_status", "not_applicable"),
            integration_error=payload.get("integration_error", ""),
            changes=dict(payload.get("changes") or {}),
            autonomy=payload.get("autonomy", "guarded"),
            requested_model=payload.get("requested_model", "auto"),
            max_agents=max(1, min(int(payload.get("max_agents", 8)), 8)),
            max_runtime_seconds=max(60, min(int(payload.get("max_runtime_seconds", 1800)), 7200)),
            deadline_at=payload.get("deadline_at", ""),
            status=payload.get("status", "queued"), plan_summary=payload.get("plan_summary", ""),
            result=payload.get("result", ""), error=payload.get("error", ""), tasks=tasks,
            events=list(payload.get("events", [])), created_at=payload.get("created_at", datetime.now().isoformat()),
            updated_at=payload.get("updated_at", datetime.now().isoformat()),
        )


class MultiAgentOrchestrator:
    """Run up to eight specialist agents with durable coordination and isolation rules."""

    MAX_CONCURRENT_AGENTS = 8
    MODES = {"cowork", "council", "swarm"}

    def __init__(
        self, jarvis: "Jarvis", store_path: Path | None = None,
        max_concurrency: int = 8, workspace_registry: WorkspaceRegistry | None = None,
        *, control_service: ControlService | None = None,
    ):
        self.jarvis = jarvis
        self.control_service = control_service
        self.stop_guard = StopGuard(control_service) if control_service is not None else None
        self.max_concurrency = max(1, min(int(max_concurrency), self.MAX_CONCURRENT_AGENTS))
        self.profiles = SPECIALIST_PROFILES.copy()
        project_root = Path(__file__).resolve().parents[2]
        database = store_path or Path(config.get("swarm.database", str(project_root / "data" / "swarm.db")))
        self.store = SwarmStore(Path(database))
        workspace_database = Path(store_path).with_name("workspaces.db") if store_path else project_root / "data" / "workspaces.db"
        self.workspaces = workspace_registry or WorkspaceRegistry(workspace_database, project_root)
        self.runs: dict[str, SwarmRun] = {}
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._project_writer_locks: dict[str, asyncio.Lock] = {}
        self._run_tasks: dict[str, asyncio.Task] = {}
        self._started = False

    async def start(self) -> None:
        """Load state and recover all unfinished work after a process restart."""
        if self._started:
            return
        self._started = True
        for payload in self.store.load_runs():
            run = SwarmRun.from_dict(payload)
            persisted_tasks = self.store.load_tasks(run.id)
            if persisted_tasks:
                run.tasks = {item["id"]: SwarmTask.from_dict(item) for item in persisted_tasks}
            run.events = self.store.load_events(run.id)
            self.runs[run.id] = run
        for run in self.runs.values():
            if run.status not in TERMINAL_STATUSES:
                continue
            reconciled = self._terminalize_remaining_tasks(
                run,
                status="cancelled",
                error=f"Parent swarm already ended as {run.status}",
            )
            if reconciled:
                self._event(
                    run,
                    "reconciled",
                    "Stale non-terminal tasks were closed during startup recovery",
                    {"task_count": reconciled},
                )
        for payload in self.store.load_unfinished():
            run = self.runs.get(payload["id"])
            if not run or run.status == "awaiting_confirmation":
                continue
            if not self._effect_allowed(run, "recovery"):
                continue
            for task in run.tasks.values():
                if task.status == "running":
                    task.status = "queued"
                    task.error = "Recovered after backend restart"
                    self._save_task(task)
            run.status = "queued"
            self._event(run, "recovered", "Recovered unfinished swarm after backend restart")
            self._spawn_execution(run)

    async def shutdown(self) -> None:
        self._started = False
        tasks = list(self._run_tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._run_tasks.clear()

    async def submit(
        self, goal: str, mode: str = "cowork", project_id: str = "default",
        autonomy: str = "guarded", model: str = "auto", max_agents: int = 8,
        max_runtime_seconds: int = 1800,
    ) -> SwarmRun:
        await self.start()
        self._require_global_effect("run_launch")
        run = self._new_run(goal, mode, project_id, autonomy, model, max_agents, max_runtime_seconds)
        self.runs[run.id] = run
        self._event(run, "submitted", f"{run.mode.title()} run accepted")
        self._spawn_execution(run)
        return run

    async def run(
        self, goal: str, mode: str = "cowork", project_id: str = "default",
        autonomy: str = "guarded", model: str = "auto", max_agents: int = 8,
        max_runtime_seconds: int = 1800,
    ) -> SwarmRun:
        """Execute inline; convenient for tests, CLI, and synchronous API routes."""
        await self.start()
        self._require_global_effect("run_launch")
        run = self._new_run(goal, mode, project_id, autonomy, model, max_agents, max_runtime_seconds)
        self.runs[run.id] = run
        self._event(run, "submitted", f"{run.mode.title()} run accepted")
        await self._execute_run(run)
        return run

    def get_run(self, run_id: str) -> SwarmRun | None:
        return self.runs.get(run_id)

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        ordered = sorted(self.runs.values(), key=lambda run: run.updated_at, reverse=True)
        return [run.to_dict() for run in ordered[:max(1, min(limit, 250))]]

    def status(self) -> dict[str, Any]:
        active = sum(run.status not in TERMINAL_STATUSES | {"awaiting_confirmation"} for run in self.runs.values())
        return {
            "started": self._started, "active_swarms": active,
            "max_concurrent_agents": self.max_concurrency,
            "active_workers": sum(not task.done() for task in self._run_tasks.values()),
            "profiles": list(self.profiles), "modes": sorted(self.MODES),
            "durable_runs": len(self.runs),
            "queue_depth": sum(
                task.status == "queued" for run in self.runs.values() for task in run.tasks.values()
            ),
            "healthy": self._started,
            "projects": len(self.workspaces.list()),
        }

    def cancel(self, run_id: str) -> SwarmRun:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.status not in TERMINAL_STATUSES:
            durable_control = self.control_service is not None
            run.status = "stopping" if durable_control else "cancelled"
            for task in run.tasks.values():
                if task.status not in TERMINAL_STATUSES:
                    task.status = "stopping" if durable_control else "cancelled"
                    task.updated_at = datetime.now().isoformat()
                    if task.agent_run_id:
                        try:
                            self.jarvis.agent_runtime.cancel(task.agent_run_id)
                        except KeyError:
                            pass
                    self._save_task(task)
            execution = self._run_tasks.get(run_id)
            if execution and not execution.done():
                execution.cancel()
            self._event(
                run,
                "stopping" if durable_control else "cancelled",
                "Swarm cancellation requested" if durable_control else "Swarm cancelled",
            )
        return run

    async def resume(self, run_id: str) -> SwarmRun:
        """Resume a recovered swarm or one whose guarded agent action was approved."""
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.status in TERMINAL_STATUSES:
            return run
        if not self._effect_allowed(run, "recovery"):
            return run
        for task in run.tasks.values():
            if task.status != "awaiting_confirmation" or not task.agent_run_id:
                continue
            agent_run = self.jarvis.agent_runtime.get_run(task.agent_run_id)
            if agent_run and agent_run.status == "completed":
                task.status, task.result = "completed", agent_run.result
                task.updated_at = datetime.now().isoformat()
                self._save_task(task)
            elif agent_run and agent_run.status == "awaiting_confirmation":
                return run
            else:
                task.status = "queued"
                self._save_task(task)
        run.status = "queued"
        self._event(run, "resumed", "Swarm execution resumed")
        await self._execute_run(run)
        return run

    def _new_run(
        self, goal: str, mode: str, project_id: str, autonomy: str,
        model: str, max_agents: int = 8, max_runtime_seconds: int = 1800,
    ) -> SwarmRun:
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(self.MODES))}")
        normalized_project = "jarvis" if project_id.strip() in {"", "default"} else project_id.strip()
        try:
            base_root = self.workspaces.resolve(normalized_project)
        except KeyError:
            # Internal/test callers retain backward compatibility; API callers validate IDs.
            base_root = Path(getattr(self.jarvis.agent_runtime, "workspace_root", Path(__file__).resolve().parents[2]))
        runtime_seconds = max(60, min(int(max_runtime_seconds), 7200))
        now = datetime.now()
        run_id = f"swarm-{uuid.uuid4().hex[:12]}"
        execution_root = base_root.resolve()
        workspace_mode = "direct"
        worktree_id = worktree_branch = ""
        integration_status = "not_applicable"
        integration_error = ""
        try:
            worktree = self.workspaces.create_worktree(normalized_project, run_id)
            execution_root = Path(worktree["root"]).resolve()
            workspace_mode = "worktree"
            worktree_id = run_id
            worktree_branch = str(worktree.get("branch") or "")
            integration_status = "working"
        except Exception as exc:
            # Non-Git and dirty projects remain usable, but their run clearly
            # reports that isolation could not be established.
            integration_status = "unavailable"
            integration_error = self._safe_error_code(exc)
            logger.info(
                "Swarm %s is using its direct project root (%s)",
                run_id,
                integration_error,
            )
        return SwarmRun(
            id=run_id, goal=goal.strip(), mode=mode,
            project_id=normalized_project, project_root=str(execution_root),
            base_root=str(base_root.resolve()), workspace_mode=workspace_mode,
            worktree_id=worktree_id, worktree_branch=worktree_branch,
            integration_status=integration_status, integration_error=integration_error,
            autonomy="full" if autonomy == "full" else "guarded",
            requested_model=model or "auto", max_agents=max(1, min(int(max_agents), 8)),
            max_runtime_seconds=runtime_seconds,
            deadline_at=(now + timedelta(seconds=runtime_seconds)).isoformat(),
            status="planning",
        )

    def _spawn_execution(self, run: SwarmRun) -> None:
        if not self._effect_allowed(run, "child"):
            return
        task = asyncio.create_task(self._execute_run(run), name=f"jarvis-{run.id}")
        self._run_tasks[run.id] = task
        task.add_done_callback(lambda _: self._run_tasks.pop(run.id, None))

    async def _execute_run(self, run: SwarmRun) -> None:
        try:
            if not self._effect_allowed(run, "run_launch"):
                return
            if not run.tasks:
                if not self._effect_allowed(run, "provider"):
                    return
                plan = self._council_plan(run) if run.mode == "council" else await self._create_plan(run)
                run.plan_summary = plan.summary
                run.tasks = {
                    task.id: SwarmTask(
                        id=f"{run.id}-{task.id}", swarm_id=run.id, title=task.title,
                        objective=task.objective, role=task.role,
                        dependencies=[f"{run.id}-{dependency}" for dependency in task.dependencies],
                        writer=task.writer,
                        model=run.requested_model,
                    )
                    for task in plan.tasks
                }
                for task in run.tasks.values():
                    self._save_task(task)
                self._event(run, "planned", run.plan_summary, {"task_count": len(run.tasks)})
            run.status = "running"
            self._save_run(run)
            await self._dispatch_graph(run)
            if run.status in {"cancelled", "awaiting_confirmation", "failed"}:
                return
            if not self._effect_allowed(run, "result_persistence"):
                return
            self._refresh_worktree(run)
            if not self._effect_allowed(run, "provider"):
                return
            run.result = await self._final_synthesis(run)
            if not self._effect_allowed(run, "result_persistence"):
                return
            run.status = "completed"
            self._event(run, "completed", "All specialist work completed")
        except asyncio.CancelledError:
            if run.status not in {"cancelled", "stopping"}:
                run.status = "queued"
                self._event(run, "paused", "Execution interrupted; durable recovery is available")
            raise
        except Exception as exc:
            code = self._safe_error_code(exc)
            logger.error("Swarm %s failed with safe code %s", run.id, code)
            run.status, run.error = "failed", code
            self._terminalize_remaining_tasks(
                run,
                status="cancelled",
                error="Parent swarm failed before this task could finish",
            )
            self._event(run, "failed", "Swarm execution failed", {"code": code})

    async def _dispatch_graph(self, run: SwarmRun) -> None:
        run_semaphore = asyncio.Semaphore(run.max_agents)
        while run.status == "running":
            if not self._effect_allowed(run, "retry"):
                return
            self._ensure_within_budget(run)
            incomplete = [task for task in run.tasks.values() if task.status not in TERMINAL_STATUSES]
            if not incomplete:
                return
            failed = {task.id for task in run.tasks.values() if task.status in {"failed", "cancelled"}}
            if failed:
                for task in incomplete:
                    if any(dep in failed for dep in task.dependencies):
                        task.status, task.error = "failed", "A dependency failed or was cancelled"
                        self._save_task(task)
                self._terminalize_remaining_tasks(
                    run,
                    status="cancelled",
                    error="Parent swarm failed before this task could start",
                )
                run.status = "failed"
                run.error = "One or more specialist tasks failed"
                self._event(run, "failed", run.error)
                return
            completed = {task.id for task in run.tasks.values() if task.status == "completed"}
            ready = [
                task for task in incomplete
                if task.status == "queued" and all(dep in completed for dep in task.dependencies)
            ]
            if not ready:
                if any(task.status == "awaiting_confirmation" for task in incomplete):
                    run.status = "awaiting_confirmation"
                    self._event(run, "approval_required", "A guarded specialist action requires approval")
                    return
                raise RuntimeError("Task graph is blocked by a cycle or missing dependency")
            async def execute_ready(task: SwarmTask) -> None:
                async with run_semaphore:
                    if not self._effect_allowed(run, "child", task_id=task.id):
                        return
                    await self._execute_task(run, task)
            await asyncio.gather(*(execute_ready(task) for task in ready))

    async def _execute_task(self, run: SwarmRun, task: SwarmTask) -> None:
        async with self._semaphore:
            self._ensure_within_budget(run)
            if run.status == "cancelled":
                return
            for attempt in range(task.attempts, task.max_attempts):
                if not self._effect_allowed(run, "retry", task_id=task.id):
                    return
                task.attempts = attempt + 1
                task.status, task.updated_at, task.error = "running", datetime.now().isoformat(), ""
                self._save_task(task)
                self._event(run, "task_started", task.title, {"task_id": task.id, "role": task.role, "attempt": task.attempts})
                try:
                    if task.role == "judge" and run.mode == "council":
                        task.result = await self._judge_council(run, task)
                        task.status = "completed"
                    else:
                        prompt = self._role_prompt(run, task)
                        if not self._effect_allowed(run, "child", task_id=task.id):
                            return
                        if task.writer:
                            lock = self._project_writer_locks.setdefault(run.project_id, asyncio.Lock())
                            async with lock:
                                agent_run = await asyncio.wait_for(
                                    self.jarvis.agent_runtime.run(
                                        prompt, model=task.model, max_steps=8, autonomy=run.autonomy,
                                        workspace_root=run.project_root,
                                    ), timeout=self._remaining_seconds(run),
                                )
                        else:
                            agent_run = await asyncio.wait_for(
                                self.jarvis.agent_runtime.run(
                                    prompt, model=task.model, max_steps=8, autonomy=run.autonomy,
                                    workspace_root=run.project_root,
                                ), timeout=self._remaining_seconds(run),
                            )
                        task.agent_run_id = agent_run.id
                        if agent_run.status == "completed":
                            task.status, task.result = "completed", agent_run.result
                        elif agent_run.status == "awaiting_confirmation":
                            task.status = "awaiting_confirmation"
                            task.result = "Approval required in the linked agent run"
                        else:
                            raise RuntimeError(agent_run.error or f"Agent ended as {agent_run.status}")
                except asyncio.CancelledError:
                    task.status = "cancelled" if run.status == "cancelled" else "queued"
                    self._save_task(task)
                    raise
                except Exception as exc:
                    task.error = self._safe_error_code(exc)
                    if task.attempts < task.max_attempts and run.status != "cancelled":
                        if not self._effect_allowed(run, "retry", task_id=task.id):
                            return
                        task.status = "queued"
                        self._event(run, "task_retry", f"Reassigning {task.title} to a fresh {task.role} agent", {"task_id": task.id, "attempt": task.attempts, "code": task.error})
                        self._save_task(task)
                        await asyncio.sleep(min(2 ** (task.attempts - 1), 4))
                        continue
                    task.status = "failed"
                finally:
                    task.updated_at = datetime.now().isoformat()
                    self._save_task(task)
                if task.status in {"completed", "awaiting_confirmation", "failed"}:
                    break
            self._event(
                run, "task_finished", task.title,
                {"task_id": task.id, "role": task.role, "status": task.status, "attempts": task.attempts, "agent_run_id": task.agent_run_id},
            )

    def _remaining_seconds(self, run: SwarmRun) -> float:
        if not run.deadline_at:
            return float(run.max_runtime_seconds)
        return max(0.01, (datetime.fromisoformat(run.deadline_at) - datetime.now()).total_seconds())

    def _refresh_worktree(self, run: SwarmRun) -> dict[str, Any]:
        if run.workspace_mode != "worktree" or not run.worktree_id:
            return run.changes
        try:
            inspection = self.workspaces.inspect_worktree(run.project_id, run.worktree_id)
            run.changes = inspection
            run.integration_error = ""
            if run.integration_status not in {"integrated", "rejected"}:
                has_changes = (
                    not bool(inspection.get("clean", True))
                    or int(inspection.get("ahead") or 0) > 0
                    or bool(inspection.get("changed_files"))
                )
                run.integration_status = "pending" if has_changes else "no_changes"
            self._save_run(run)
            return inspection
        except Exception as exc:
            run.integration_status = "blocked"
            run.integration_error = self._safe_error_code(exc)
            self._save_run(run)
            return run.changes

    def refresh_worktree(self, run_id: str) -> SwarmRun:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        self._refresh_worktree(run)
        return run

    async def integrate(self, run_id: str, strategy: str = "ff-only") -> SwarmRun:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.status not in TERMINAL_STATUSES:
            raise RuntimeError("A running swarm cannot be integrated")
        if run.workspace_mode != "worktree" or not run.worktree_id:
            raise RuntimeError(run.integration_error or "This swarm does not have an isolated worktree")
        if not self._effect_allowed(run, "integration"):
            return run
        inspection = self._refresh_worktree(run)
        has_changes = (
            not bool(inspection.get("clean", True))
            or int(inspection.get("ahead") or 0) > 0
            or bool(inspection.get("changed_files"))
        )
        if not has_changes:
            run.integration_status = "no_changes"
            self._event(run, "integration_skipped", "The isolated mission produced no file changes")
            return run
        try:
            await asyncio.to_thread(
                self.workspaces.commit_worktree,
                run.project_id, run.worktree_id,
                f"JARVIS swarm: {run.goal[:72]}",
            )
            integrated = await asyncio.to_thread(
                self.workspaces.integrate_worktree,
                run.project_id, run.worktree_id, strategy,
            )
            run.changes = integrated
            run.integration_status = "integrated"
            run.integration_error = ""
            self._event(run, "integrated", "Isolated mission changes were integrated into the project")
        except Exception as exc:
            run.integration_status = "blocked"
            run.integration_error = self._safe_error_code(exc)
            self._event(run, "integration_blocked", "Integration was refused by the safety gate", {"code": run.integration_error})
            raise RuntimeError("integration_blocked") from exc
        try:
            await asyncio.to_thread(self.workspaces.cleanup_worktree, run.project_id, run.worktree_id)
        except Exception as exc:
            # Integration already succeeded. Retaining the worktree is safe and
            # preferable to misreporting the applied changes as a failed merge.
            run.integration_error = "cleanup_deferred"
            self._event(run, "cleanup_deferred", "Integrated worktree cleanup was deferred", {"code": self._safe_error_code(exc)})
        return run

    async def reject_integration(self, run_id: str) -> SwarmRun:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.status not in TERMINAL_STATUSES:
            raise RuntimeError("A running swarm integration cannot be rejected")
        if run.workspace_mode != "worktree" or not run.worktree_id:
            raise RuntimeError("This swarm does not have an isolated worktree")
        # Rejection is intentionally non-destructive. Keep the isolated branch
        # available for audit/recovery instead of force-removing user-visible work.
        run.integration_status = "rejected"
        run.integration_error = ""
        self._event(run, "integration_rejected", "The isolated mission changes were rejected and retained for inspection")
        return run

    def _ensure_within_budget(self, run: SwarmRun) -> None:
        if self._remaining_seconds(run) <= 0.02:
            raise TimeoutError(f"Mission exceeded its {run.max_runtime_seconds}-second runtime budget")

    def _role_prompt(self, run: SwarmRun, task: SwarmTask) -> str:
        dependency_results = [
            {"title": run.tasks[dep].title, "role": run.tasks[dep].role, "result": run.tasks[dep].result}
            for dep in task.dependencies if dep in run.tasks
        ]
        return f"""You are the JARVIS {task.role.upper()} specialist.
Role charter: {self.profiles[task.role]}
Overall goal: {run.goal}
Project: {run.project_id}
Workspace root: {run.project_root}
Assigned task: {task.title}
Objective: {task.objective}
Dependency outputs: {json.dumps(dependency_results, ensure_ascii=False)}

Work only on this assignment. Use tools for evidence and implementation. Do not duplicate another role's scope.
Return a concise result with work performed, verification evidence, files/artifacts, and remaining risks."""

    async def _create_plan(self, run: SwarmRun) -> SwarmPlan:
        roles = "\n".join(f"- {name}: {description}" for name, description in self.profiles.items())
        prompt = f"""Decompose this goal for a coordinated JARVIS {run.mode} team.
Use at most 8 tasks and only these roles. Independent tasks should have no dependencies so they run concurrently.
Use writer=true only when a task can modify project files or external state. Include a reviewer or tester after implementation where useful.

Roles:
{roles}

Return strict JSON only:
{{"summary":"...","tasks":[{{"id":"task-1","title":"...","objective":"...","role":"coder","dependencies":[],"writer":true}}]}}

Goal: {run.goal}
Project: {run.project_id}"""
        try:
            routing = await self.jarvis.route_model(run.goal, run.requested_model)
            async with NVIDIAClient() as client:
                response = await client.chat_completion(
                    [
                        {"role": "system", "content": "You are a multi-agent task planner. Return strict JSON without markdown."},
                        {"role": "user", "content": prompt},
                    ],
                    model=routing.model, temperature=0.1, max_tokens=1800,
                )
            plan = SwarmPlan.model_validate(self._parse_json(response["choices"][0]["message"]["content"]))
            return self._sanitize_plan(plan)
        except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            logger.warning(
                "Swarm planner output invalid; using fallback (%s)",
                self._safe_error_code(exc),
            )
            return self._fallback_plan(run)

    def _sanitize_plan(self, plan: SwarmPlan) -> SwarmPlan:
        tasks = plan.tasks[:self.MAX_CONCURRENT_AGENTS]
        if len({task.id for task in tasks}) != len(tasks):
            raise ValueError("Swarm plan contains duplicate task IDs")
        valid_ids = {task.id for task in tasks}
        for task in tasks:
            if task.role not in self.profiles:
                task.role = "researcher"
            task.dependencies = [dep for dep in dict.fromkeys(task.dependencies) if dep in valid_ids and dep != task.id]
        return SwarmPlan(summary=plan.summary, tasks=tasks)

    def _fallback_plan(self, run: SwarmRun) -> SwarmPlan:
        if run.mode == "swarm":
            tasks = [
                PlannedTask(id="task-1", title="Research requirements", objective=run.goal, role="researcher"),
                PlannedTask(id="task-2", title="Design solution", objective=run.goal, role="designer", writer=True),
                PlannedTask(id="task-3", title="Implement solution", objective=run.goal, role="coder", dependencies=["task-1"], writer=True),
                PlannedTask(id="task-4", title="Verify outcome", objective=run.goal, role="tester", dependencies=["task-2", "task-3"]),
                PlannedTask(id="task-5", title="Independent review", objective=run.goal, role="reviewer", dependencies=["task-4"]),
            ]
        else:
            tasks = [
                PlannedTask(id="task-1", title="Analyze and coordinate", objective=run.goal, role="manager"),
                PlannedTask(id="task-2", title="Produce specialist solution", objective=run.goal, role="coder", dependencies=["task-1"], writer=True),
                PlannedTask(id="task-3", title="Test the solution", objective=run.goal, role="tester", dependencies=["task-2"]),
                PlannedTask(id="task-4", title="Review the result", objective=run.goal, role="reviewer", dependencies=["task-3"]),
            ]
        return SwarmPlan(summary="Coordinate specialist agents and independently verify the outcome.", tasks=tasks)

    def _council_plan(self, run: SwarmRun) -> SwarmPlan:
        members = ["coder", "researcher", "designer", "reviewer", "devops"]
        tasks = [
            PlannedTask(
                id=f"member-{index}", title=f"Independent {role} analysis",
                objective=f"Independently solve or assess: {run.goal}", role=role,
            )
            for index, role in enumerate(members, start=1)
        ]
        tasks.append(PlannedTask(
            id="judge", title="Judge the council", objective="Compare all council proposals and decide by evidence.",
            role="judge", dependencies=[task.id for task in tasks],
        ))
        return SwarmPlan(summary="Collect independent specialist proposals, then have a judge synthesize the strongest answer.", tasks=tasks)

    async def _judge_council(self, run: SwarmRun, task: SwarmTask) -> str:
        proposals = [
            {"role": candidate.role, "title": candidate.title, "result": candidate.result}
            for candidate in run.tasks.values() if candidate.id in task.dependencies
        ]
        routing = await self.jarvis.route_model(run.goal, run.requested_model)
        async with NVIDIAClient() as client:
            response = await client.chat_completion(
                [
                    {"role": "system", "content": "You are JARVIS's independent council judge. Decide by evidence, surface disagreements, and never fabricate consensus."},
                    {"role": "user", "content": f"Goal: {run.goal}\n\nCouncil proposals:\n{json.dumps(proposals, ensure_ascii=False, indent=2)}\n\nReturn the best synthesized decision, rationale, risks, and next actions."},
                ],
                model=routing.model, temperature=0.2, max_tokens=2200,
            )
        return response["choices"][0]["message"]["content"]

    async def _final_synthesis(self, run: SwarmRun) -> str:
        if run.mode == "council":
            judge = next((task for task in run.tasks.values() if task.role == "judge"), None)
            if judge and judge.result:
                return judge.result
        evidence = [
            {"role": task.role, "title": task.title, "result": task.result}
            for task in run.tasks.values()
        ]
        routing = await self.jarvis.route_model(run.goal, run.requested_model)
        async with NVIDIAClient() as client:
            response = await client.chat_completion(
                [
                    {"role": "system", "content": "You are JARVIS's manager. Synthesize completed specialist outputs into one evidence-based result. Do not claim work not shown."},
                    {"role": "user", "content": f"Goal: {run.goal}\nMode: {run.mode}\nSpecialist outputs:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\nGive Ahmed the integrated outcome, verification, artifacts, risks, and concise next actions."},
                ],
                model=routing.model, temperature=0.2, max_tokens=2400,
            )
        return response["choices"][0]["message"]["content"]

    def _event(self, run: SwarmRun, event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        timestamp = datetime.now().isoformat()
        event = {"timestamp": timestamp, "event_type": event_type, "message": message, "data": data or {}}
        # The parent row must exist before its first event due to the FK constraint.
        self._save_run(run)
        sequence = self.store.append_event(run.id, timestamp, event_type, {"message": message, "data": data or {}})
        event["sequence"] = sequence
        run.events.append(event)
        run.updated_at = timestamp
        self._save_run(run)

    def _save_run(self, run: SwarmRun) -> None:
        self.store.save_run(run.to_dict())

    def _save_task(self, task: SwarmTask) -> None:
        self.store.save_task(task.to_dict())

    def _terminalize_remaining_tasks(
        self,
        run: SwarmRun,
        *,
        status: str,
        error: str,
    ) -> int:
        """Close orphaned task rows whenever their parent run is terminal."""

        changed = 0
        timestamp = datetime.now().isoformat()
        for task in run.tasks.values():
            if task.status in TERMINAL_STATUSES:
                continue
            task.status = status
            task.error = error
            task.updated_at = timestamp
            self._save_task(task)
            changed += 1
        return changed

    def _require_global_effect(self, boundary: str) -> None:
        if self.stop_guard is not None:
            self.stop_guard.require_effect_allowed(boundary=boundary)

    def _effect_allowed(
        self, run: SwarmRun, boundary: str, *, task_id: str | None = None
    ) -> bool:
        if self.control_service is None:
            return True
        try:
            snapshot = StopGuard(
                self.control_service, run_id=run.id
            ).require_effect_allowed(boundary=boundary)
            if task_id is not None:
                self.control_service.record_runtime_event(
                    action="swarm_boundary",
                    outcome="allowed",
                    boundary=boundary,
                    snapshot=snapshot,
                    run_id=run.id,
                    task_id=task_id,
                    applied=False,
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
                "control_blocked",
                "Durable control state blocked a new swarm effect",
                {
                    "code": "control_blocked",
                    "boundary": boundary,
                    "task_id": task_id,
                    "revision": None if snapshot is None else snapshot.revision,
                },
            )
            return False

    @staticmethod
    def _safe_error_code(exc: BaseException) -> str:
        if isinstance(exc, ControlBlockedError):
            return "control_blocked"
        name = type(exc).__name__.removesuffix("Error") or "runtime"
        normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", name).casefold()
        return f"{normalized}_error"[:128]

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise json.JSONDecodeError("No JSON object", cleaned, 0)
        return json.loads(cleaned[start:end + 1])


# Friendly alias for API/integration code.
SwarmRuntime = MultiAgentOrchestrator
SwarmCoordinator = MultiAgentOrchestrator
