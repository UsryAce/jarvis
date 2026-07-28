import asyncio
import tempfile
import unittest
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.core.model_router import RouteDecision
from src.core.swarm import (
    MultiAgentOrchestrator,
    PlannedTask,
    SwarmPlan,
    SwarmTask,
)
from src.core.workspaces import WorkspaceRegistry


@dataclass
class FakeAgentRun:
    id: str
    status: str = "completed"
    result: str = "Specialist completed the assignment."
    error: str = ""


class FakeAgentRuntime:
    def __init__(self):
        self.calls = 0
        self.cancelled = []

    async def run(self, *_args, **_kwargs):
        self.calls += 1
        return FakeAgentRun(f"agent-{self.calls}")

    def cancel(self, run_id):
        self.cancelled.append(run_id)

    def get_run(self, _run_id):
        return None


class FakeJarvis:
    def __init__(self, agent_runtime=None):
        self.agent_runtime = agent_runtime or FakeAgentRuntime()

    async def route_model(self, _goal, _model):
        return RouteDecision(
            model="z-ai/glm-5.2", task_category="general",
            reason="swarm test", auto_mode=True,
        )


def independent_plan(count=8, *, writer=False):
    return SwarmPlan(
        summary="Run independent specialists.",
        tasks=[
            PlannedTask(
                id=f"task-{index}", title=f"Task {index}",
                objective=f"Complete assignment {index}", role="coder" if writer else "researcher",
                writer=writer,
            )
            for index in range(count)
        ],
    )


class SwarmRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def runtime(self, jarvis=None, *, max_concurrency=8, filename="swarm.db"):
        return MultiAgentOrchestrator(
            jarvis or FakeJarvis(), Path(self.tempdir.name) / filename,
            max_concurrency=max_concurrency,
        )

    async def test_max_eight_agents_and_semaphore_enforces_cap(self):
        runtime = self.runtime(max_concurrency=99)
        self.assertEqual(runtime.max_concurrency, 8)
        self.assertEqual(runtime.status()["max_concurrent_agents"], 8)
        self.assertEqual(len(runtime._sanitize_plan(independent_plan(12)).tasks), 8)

        active = 0
        peak = 0
        release = asyncio.Event()

        async def measured_run(*_args, **_kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await release.wait()
            active -= 1
            return FakeAgentRun(f"agent-{peak}-{active}")

        runtime.jarvis.agent_runtime.run = measured_run
        runtime._create_plan = AsyncMock(return_value=independent_plan(8))
        runtime._final_synthesis = AsyncMock(return_value="Integrated result")
        execution = asyncio.create_task(runtime.run("parallel work", mode="swarm"))
        for _ in range(100):
            if peak == 8:
                break
            await asyncio.sleep(0.005)
        self.assertEqual(peak, 8)
        release.set()
        run = await execution
        self.assertEqual(run.status, "completed")
        await runtime.shutdown()

    def test_read_only_swarm_fallback_has_no_writer_tasks(self):
        runtime = self.runtime()
        run = SimpleNamespace(
            mode="swarm",
            goal="Inspect Jarvis runtime and provider health without changing files",
        )
        plan = runtime._fallback_plan(run)
        self.assertEqual(len(plan.tasks), 4)
        self.assertFalse(any(task.writer for task in plan.tasks))

    async def test_dependencies_start_only_after_prerequisite_completes(self):
        runtime = self.runtime()
        order = []

        async def recorded_run(prompt, **_kwargs):
            label = "first" if "First" in prompt else "second"
            order.append(f"{label}:start")
            await asyncio.sleep(0)
            order.append(f"{label}:end")
            return FakeAgentRun(f"agent-{label}")

        runtime.jarvis.agent_runtime.run = recorded_run
        runtime._create_plan = AsyncMock(return_value=SwarmPlan(
            summary="Ordered work",
            tasks=[
                PlannedTask(id="first", title="First", objective="First", role="researcher"),
                PlannedTask(
                    id="second", title="Second", objective="Second", role="tester",
                    dependencies=["first"],
                ),
            ],
        ))
        runtime._final_synthesis = AsyncMock(return_value="Done")

        run = await runtime.run("ordered goal")

        self.assertEqual(order, ["first:start", "first:end", "second:start", "second:end"])
        self.assertEqual(run.status, "completed")
        await runtime.shutdown()

    async def test_per_mission_concurrency_limit_is_enforced(self):
        runtime = self.runtime(max_concurrency=8)
        active = 0
        peak = 0

        async def measured_run(*_args, **_kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
            return FakeAgentRun(f"agent-{peak}-{active}")

        runtime.jarvis.agent_runtime.run = measured_run
        runtime._create_plan = AsyncMock(return_value=independent_plan(8))
        runtime._final_synthesis = AsyncMock(return_value="Limited result")

        run = await runtime.run("bounded parallel work", mode="swarm", max_agents=3)

        self.assertEqual(run.status, "completed")
        self.assertEqual(run.max_agents, 3)
        self.assertEqual(peak, 3)
        await runtime.shutdown()

    async def test_writers_for_same_project_are_serialized(self):
        runtime = self.runtime()
        active_writers = 0
        peak_writers = 0

        async def writer_run(*_args, **_kwargs):
            nonlocal active_writers, peak_writers
            active_writers += 1
            peak_writers = max(peak_writers, active_writers)
            await asyncio.sleep(0.015)
            active_writers -= 1
            return FakeAgentRun(f"writer-{peak_writers}-{active_writers}")

        runtime.jarvis.agent_runtime.run = writer_run
        runtime._create_plan = AsyncMock(return_value=independent_plan(4, writer=True))
        runtime._final_synthesis = AsyncMock(return_value="Writers finished")

        run = await runtime.run("modify one project", mode="swarm", project_id="project-a")

        self.assertEqual(run.status, "completed")
        self.assertEqual(peak_writers, 1)
        await runtime.shutdown()

    async def test_writer_mission_uses_worktree_and_requires_explicit_integration(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Swarm Test"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.email", "swarm@test.local"], cwd=project, check=True)
            (project / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "base.txt"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=project, check=True, capture_output=True)

            registry = WorkspaceRegistry(root / "workspaces.db", project)

            class WritingRuntime(FakeAgentRuntime):
                async def run(self, *_args, **kwargs):
                    workspace = Path(kwargs["workspace_root"])
                    (workspace / "mission.txt").write_text("isolated\n", encoding="utf-8")
                    return FakeAgentRun("writer-agent")

            runtime = MultiAgentOrchestrator(
                FakeJarvis(WritingRuntime()), root / "swarm.db",
                workspace_registry=registry,
            )
            runtime._create_plan = AsyncMock(return_value=independent_plan(1, writer=True))
            runtime._final_synthesis = AsyncMock(return_value="Ready for review")

            run = await runtime.run("make an isolated change", mode="swarm", project_id="jarvis")

            self.assertEqual(run.status, "completed")
            self.assertEqual(run.workspace_mode, "worktree")
            self.assertEqual(run.integration_status, "pending")
            self.assertFalse((project / "mission.txt").exists())
            self.assertTrue((Path(run.project_root) / "mission.txt").exists())

            integrated = await runtime.integrate(run.id)
            self.assertEqual(integrated.integration_status, "integrated")
            self.assertEqual((project / "mission.txt").read_text(encoding="utf-8"), "isolated\n")
            await runtime.shutdown()

    async def test_cancel_stops_background_swarm_and_marks_unfinished_tasks(self):
        runtime = self.runtime()
        started = asyncio.Event()
        blocked = asyncio.Event()

        async def blocking_run(*_args, **_kwargs):
            started.set()
            await blocked.wait()
            return FakeAgentRun("agent-blocked")

        runtime.jarvis.agent_runtime.run = blocking_run
        runtime._create_plan = AsyncMock(return_value=independent_plan(3))
        runtime._final_synthesis = AsyncMock(return_value="Should not synthesize")

        run = await runtime.submit("cancel this", mode="swarm")
        await asyncio.wait_for(started.wait(), timeout=1)
        runtime.cancel(run.id)
        await asyncio.sleep(0)

        self.assertEqual(run.status, "cancelled")
        self.assertTrue(run.tasks)
        self.assertTrue(all(task.status == "cancelled" for task in run.tasks.values()))
        runtime._final_synthesis.assert_not_awaited()
        blocked.set()
        await runtime.shutdown()

    async def test_unfinished_run_recovers_from_sqlite_after_restart(self):
        database = Path(self.tempdir.name) / "recovery.db"
        first = MultiAgentOrchestrator(FakeJarvis(), database)
        run = first._new_run("recover me", "cowork", "project-r", "guarded", "auto")
        run.status = "running"
        task = SwarmTask(
            id=f"{run.id}-task-1", swarm_id=run.id, title="Recovered task",
            objective="Finish after restart", role="researcher", status="running",
        )
        run.tasks[task.id] = task
        first.runs[run.id] = run
        first._save_run(run)
        first._save_task(task)

        recovered = MultiAgentOrchestrator(FakeJarvis(), database)
        recovered._final_synthesis = AsyncMock(return_value="Recovered result")
        await recovered.start()
        for _ in range(100):
            loaded = recovered.get_run(run.id)
            if loaded and loaded.status == "completed":
                break
            await asyncio.sleep(0.01)

        loaded = recovered.get_run(run.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.status, "completed")
        self.assertEqual(loaded.result, "Recovered result")
        self.assertTrue(any(event["event_type"] == "recovered" for event in loaded.events))
        self.assertEqual(next(iter(loaded.tasks.values())).status, "completed")
        await recovered.shutdown()

    async def test_partial_failure_preserves_success_and_blocks_dependents(self):
        runtime = self.runtime()

        async def mixed_run(prompt, **_kwargs):
            if "Failing task" in prompt:
                return FakeAgentRun("agent-bad", status="failed", result="", error="intentional failure")
            return FakeAgentRun("agent-good", result="verified evidence")

        runtime.jarvis.agent_runtime.run = mixed_run
        runtime._create_plan = AsyncMock(return_value=SwarmPlan(
            summary="Exercise partial failure",
            tasks=[
                PlannedTask(id="good", title="Good task", objective="Succeed", role="researcher"),
                PlannedTask(id="bad", title="Failing task", objective="Fail", role="researcher"),
                PlannedTask(
                    id="dependent", title="Dependent task", objective="Needs bad task",
                    role="tester", dependencies=["bad"],
                ),
            ],
        ))
        runtime._final_synthesis = AsyncMock(return_value="Must not synthesize")

        run = await runtime.run("handle partial failure", mode="swarm")
        by_title = {task.title: task for task in run.tasks.values()}

        self.assertEqual(run.status, "failed")
        self.assertEqual(by_title["Good task"].status, "completed")
        self.assertEqual(by_title["Good task"].result, "verified evidence")
        self.assertEqual(by_title["Failing task"].status, "failed")
        self.assertEqual(by_title["Dependent task"].status, "failed")
        self.assertIn("dependency", by_title["Dependent task"].error.lower())
        runtime._final_synthesis.assert_not_awaited()
        await runtime.shutdown()

    async def test_failed_specialist_is_reassigned_and_recovers(self):
        runtime = self.runtime()
        attempts = 0

        async def flaky_run(*_args, **_kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return FakeAgentRun(f"agent-{attempts}", status="failed", result="", error="temporary outage")
            return FakeAgentRun("agent-3", result="recovered evidence")

        runtime.jarvis.agent_runtime.run = flaky_run
        runtime._create_plan = AsyncMock(return_value=independent_plan(1))
        runtime._final_synthesis = AsyncMock(return_value="Recovered mission")

        run = await runtime.run("recover a flaky specialist", mode="swarm")

        task = next(iter(run.tasks.values()))
        self.assertEqual(run.status, "completed")
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.attempts, 3)
        self.assertTrue(any(event["event_type"] == "task_retry" for event in run.events))
        await runtime.shutdown()


if __name__ == "__main__":
    unittest.main()
