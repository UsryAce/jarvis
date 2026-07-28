import unittest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.core.agent import AgentPlan, AgentRuntime, AgentStep
from src.core.model_router import RouteDecision


class FakeJarvis:
    system_prompt = "You are Jarvis."
    memory = None

    def __init__(self):
        self.conversation_history = []

    async def route_model(self, goal, model):
        return RouteDecision(model="z-ai/glm-5.2", task_category="general", reason="test", auto_mode=True)

    async def execute_skill(self, name, params):
        return {"skill": name, "params": params}

    async def recall(self, query, limit):
        return []


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def runtime(self):
        return AgentRuntime(FakeJarvis(), Path(self.tempdir.name) / "agent.db")

    async def test_read_tool_run_completes_with_trace(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="inspect system", summary="Inspect live state",
            steps=[AgentStep(id="step-1", description="Read system", tool="system_info", arguments={"action": "cpu"})],
        ))
        runtime._synthesize = AsyncMock(return_value="System inspected.")

        run = await runtime.run("inspect system")

        self.assertEqual(run.status, "completed")
        self.assertIn("Executed 1 verified tool step: system_info", run.result)
        self.assertIn("System evidence", run.result)
        runtime._synthesize.assert_not_awaited()
        self.assertEqual(run.observations[0]["tool"], "system_info")
        self.assertTrue(any(event["stage"] == "tool" for event in run.events))

    async def test_write_tool_requires_approval_then_resumes(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create", arguments={"title": "Test", "content": "Agent note"})],
        ))
        runtime._execute_tool = AsyncMock(return_value="Note saved")
        runtime._synthesize = AsyncMock(return_value="The note was saved.")

        run = await runtime.run("save note")
        self.assertEqual(run.status, "awaiting_confirmation")
        runtime._execute_tool.assert_not_awaited()

        resumed = await runtime.approve(run.id, ["step-1"])
        self.assertEqual(resumed.status, "completed")
        runtime._execute_tool.assert_awaited_once()

    def test_tool_catalog_marks_mutations(self):
        tools = {item["name"]: item["risk"] for item in self.runtime().list_tools()}
        self.assertEqual(tools["web_search"], "read")
        self.assertEqual(tools["note_create"], "write")
        self.assertEqual(tools["project_create"], "write")
        self.assertEqual(tools["github_status"], "read")

    async def test_full_auto_can_write_only_inside_workspace(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        result = await runtime._execute_tool("workspace_write", {"path": "demo.txt", "content": "ready"})
        self.assertEqual(result["written_chars"], 5)
        self.assertEqual((runtime.workspace_root / "demo.txt").read_text(), "ready")
        with self.assertRaises(PermissionError):
            await runtime._execute_tool("workspace_write", {"path": "../escape.txt", "content": "blocked"})

    async def test_project_creator_builds_runnable_website_inside_workspace(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        result = await runtime._execute_tool(
            "project_create",
            {"name": "Launch Site", "kind": "website", "description": "A real starter site."},
        )
        project = runtime.workspace_root / "projects" / "launch-site"
        self.assertTrue(result["created"])
        self.assertTrue((project / "index.html").is_file())
        self.assertIn("Launch Site", (project / "index.html").read_text(encoding="utf-8"))
        self.assertTrue((project / "styles.css").is_file())

    def test_project_goal_generates_real_execution_plan(self):
        plan = self.runtime()._fallback_plan("Create a website called Aurora and put it on GitHub")
        self.assertEqual([step.tool for step in plan.steps], [
            "project_create", "git_init", "git_commit", "github_status", "github_create_repo", "github_push",
        ])
        full_run = type("Run", (), {"autonomy": "full", "goal": "Create Aurora and put it on GitHub"})()
        guarded_run = type("Run", (), {"autonomy": "guarded", "goal": "Create Aurora and put it on GitHub"})()
        self.assertFalse(self.runtime()._requires_confirmation(full_run, plan.steps[4]))
        self.assertTrue(self.runtime()._requires_confirmation(guarded_run, plan.steps[4]))
        self.assertEqual(plan.steps[0].arguments["name"], "aurora")

    async def test_known_github_goal_uses_deterministic_fast_plan(self):
        plan = await self.runtime()._create_plan("Check my GitHub connection", "z-ai/glm-5.2", 3)
        self.assertEqual([step.tool for step in plan.steps], ["github_status"])

    async def test_git_status_goal_uses_read_only_fast_plan(self):
        plan = await self.runtime()._create_plan(
            "Report the current Git branch and working-tree status without changing files",
            "z-ai/glm-5.2",
            3,
        )
        self.assertEqual([step.tool for step in plan.steps], ["git_status"])

    async def test_open_google_uses_local_fast_plan_without_model(self):
        runtime = self.runtime()
        plan = await runtime._create_plan("Jarvis, can you open Google for me?", "z-ai/glm-5.2", 3)
        self.assertEqual([step.tool for step in plan.steps], ["open_url"])
        self.assertEqual(plan.steps[0].arguments["url"], "https://www.google.com/")

    async def test_workspace_search_has_python_fallback_without_ripgrep(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        (runtime.workspace_root / "src").mkdir()
        (runtime.workspace_root / "src" / "sample.py").write_text("alpha\nneedle here\nomega\n", encoding="utf-8")
        with patch("src.core.agent.shutil.which", return_value=None):
            result = await runtime._execute_tool("workspace_search", {"query": "needle", "path": "src", "glob": "*.py"})
        self.assertEqual(result["fallback"], "python")
        self.assertIn("src\\sample.py:2:needle here", result["stdout"])

    def test_execution_receipt_uses_verified_tool_data(self):
        runtime = self.runtime()
        run = type("Run", (), {
            "goal": "Check my GitHub connection",
            "workspace_root": str(Path(self.tempdir.name).resolve()),
            "observations": [{"tool": "github_status", "ok": True, "data": {"authenticated": True}}],
        })()
        receipt = runtime._execution_receipt(run)
        self.assertIn("GitHub CLI is authenticated", receipt)

    def test_action_intent_detects_real_work(self):
        self.assertTrue(AgentRuntime.is_action_goal("Fix the dashboard and run its tests"))
        self.assertTrue(AgentRuntime.is_action_goal("Create a GitHub repository"))
        self.assertFalse(AgentRuntime.is_action_goal("What is a GitHub repository?"))

    async def test_adaptive_loop_can_add_and_execute_verification_step(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="create proof", summary="Create proof",
            steps=[AgentStep(id="step-1", description="Write proof", tool="workspace_write", arguments={"path": "proof.txt", "content": "ready"})],
        ))
        runtime._continue_plan = AsyncMock(side_effect=[
            [AgentStep(id="step-2", description="Verify proof", tool="workspace_read", arguments={"path": "proof.txt"})],
            [],
        ])
        runtime._synthesize = AsyncMock(return_value="Proof created and verified.")
        run = await runtime.run("Build proof project", autonomy="full", max_steps=3)
        self.assertEqual(run.status, "completed")
        self.assertEqual([item["tool"] for item in run.observations], ["workspace_write", "workspace_read"])
        self.assertIn("ready", run.observations[1]["result"])

    def test_created_project_path_flows_into_later_git_steps(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        project = runtime.workspace_root / "projects" / "agent-power-proof"
        project.mkdir(parents=True)
        run = type("Run", (), {
            "workspace_root": str(runtime.workspace_root),
            "observations": [{
                "tool": "project_create", "ok": True,
                "data": {"path": "projects/agent-power-proof"},
            }],
        })()
        step = AgentStep(
            id="step-2", description="Initialize git", tool="git_init",
            arguments={"path": "Agent Power Proof"},
        )
        runtime._resolve_step_context(run, step)
        self.assertEqual(step.arguments["path"], "projects/agent-power-proof")

    async def test_run_persists_and_loads_after_restart(self):
        database = Path(self.tempdir.name) / "agent.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="persist", summary="Persist run",
            steps=[AgentStep(id="step-1", description="Reason")],
        ))
        runtime._synthesize = AsyncMock(return_value="Persisted.")
        run = await runtime.run("persist")

        recovered = AgentRuntime(FakeJarvis(), database)
        await recovered.start()
        try:
            self.assertEqual(recovered.get_run(run.id).result, "Persisted.")
            self.assertEqual(recovered.get_run(run.id).status, "completed")
        finally:
            await recovered.shutdown()


if __name__ == "__main__":
    unittest.main()
