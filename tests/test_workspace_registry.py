import tempfile
import unittest
import subprocess
from pathlib import Path

from src.core.agent import AgentRuntime
from src.core.workspaces import WorkspaceRegistry

from tests.test_agent_runtime import FakeJarvis


class WorkspaceRegistryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(dir=Path.home())
        self.root = Path(self.tempdir.name)
        self.jarvis_root = self.root / "jarvis"
        self.project_root = self.root / "project-two"
        self.jarvis_root.mkdir()
        self.project_root.mkdir()
        self.registry = WorkspaceRegistry(self.root / "workspaces.db", self.jarvis_root)

    def tearDown(self):
        self.tempdir.cleanup()

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True,
        ).stdout.strip()

    def _init_repo(self, root: Path) -> None:
        self._git(root, "init", "-b", "main")
        self._git(root, "config", "user.name", "Workspace Test")
        self._git(root, "config", "user.email", "workspace@test.local")
        (root / "base.txt").write_text("base\n", encoding="utf-8")
        self._git(root, "add", "base.txt")
        self._git(root, "commit", "-m", "initial")

    def test_registers_and_resolves_multiple_projects(self):
        project = self.registry.register("project-two", "Project Two", self.project_root)

        self.assertEqual(project["id"], "project-two")
        self.assertEqual(self.registry.resolve("project-two"), self.project_root.resolve())
        self.assertEqual({item["id"] for item in self.registry.list()}, {"jarvis", "project-two"})

    def test_blocks_workspace_outside_user_home(self):
        outside = Path.home().parent
        with self.assertRaises(PermissionError):
            self.registry.register("outside", "Outside", outside)

    async def test_agent_tools_are_scoped_to_selected_project(self):
        runtime = AgentRuntime(FakeJarvis(), self.root / "agent.db")
        runtime.workspace_root = self.jarvis_root.resolve()

        await runtime._execute_tool(
            "workspace_write", {"path": "isolated.txt", "content": "project two"},
            self.project_root,
        )

        self.assertEqual((self.project_root / "isolated.txt").read_text(), "project two")
        self.assertFalse((self.jarvis_root / "isolated.txt").exists())
        with self.assertRaises(PermissionError):
            await runtime._execute_tool(
                "workspace_write", {"path": "../escape.txt", "content": "blocked"},
                self.project_root,
            )

    def test_worktree_create_isolate_commit_integrate_and_cleanup(self):
        self._init_repo(self.project_root)
        self.registry.register("project-two", "Project Two", self.project_root)

        created = self.registry.create_worktree("project-two", "run-123")
        # Creation is idempotent and never creates a second branch/tree.
        self.assertEqual(self.registry.create_worktree("project-two", "run-123")["root"], created["root"])
        mission_root = Path(created["root"])
        self.assertTrue(mission_root.is_dir())
        self.assertEqual(created["branch"], "jarvis/run-123")

        (mission_root / "mission.txt").write_text("isolated\n", encoding="utf-8")
        self.assertFalse((self.project_root / "mission.txt").exists())
        inspection = self.registry.inspect_worktree("project-two", "run-123")
        self.assertIn("mission.txt", inspection["changed_files"])

        committed = self.registry.commit_worktree("project-two", "run-123", "mission result")
        self.assertEqual(committed["status"], "committed")
        self.assertTrue(committed["clean"])
        self.assertEqual(committed["ahead"], 1)

        integrated = self.registry.integrate_worktree("project-two", "run-123", "ff-only")
        self.assertEqual(integrated["status"], "integrated")
        self.assertEqual((self.project_root / "mission.txt").read_text(encoding="utf-8"), "isolated\n")

        cleaned = self.registry.cleanup_worktree("project-two", "run-123")
        self.assertEqual(cleaned["status"], "cleaned")
        self.assertFalse(mission_root.exists())
        # Cleanup is also idempotent and history remains auditable in SQLite.
        self.assertEqual(self.registry.cleanup_worktree("project-two", "run-123")["status"], "cleaned")
        self.assertEqual(len(self.registry.list_worktrees("project-two")), 1)

    def test_worktree_cherry_pick_integration(self):
        self._init_repo(self.project_root)
        self.registry.register("project-two", "Project Two", self.project_root)
        created = self.registry.create_worktree("project-two", "cherry-run")
        (Path(created["root"]) / "picked.txt").write_text("picked\n", encoding="utf-8")
        self.registry.commit_worktree("project-two", "cherry-run", "picked result")

        integrated = self.registry.integrate_worktree("project-two", "cherry-run")

        self.assertEqual(integrated["status"], "integrated")
        self.assertTrue((self.project_root / "picked.txt").exists())
        self.registry.cleanup_worktree("project-two", "cherry-run")

    def test_create_recovers_worktree_created_before_database_write(self):
        self._init_repo(self.project_root)
        self.registry.register("project-two", "Project Two", self.project_root)
        original = self.registry.create_worktree("project-two", "recover-run")
        # Simulate a process dying between Git's successful worktree creation and
        # registry persistence, without deleting or rewriting any Git state.
        with self.registry._connection() as connection:
            connection.execute(
                "DELETE FROM mission_worktrees WHERE project_id = ? AND run_id = ?",
                ("project-two", "recover-run"),
            )

        recovered = self.registry.create_worktree("project-two", "recover-run")

        self.assertEqual(recovered["root"], original["root"])
        self.assertTrue(recovered["metadata"]["recovered"])
        self.registry.cleanup_worktree("project-two", "recover-run")

    def test_worktree_rejects_non_git_bases(self):
        self.registry.register("project-two", "Project Two", self.project_root)
        with self.assertRaises(subprocess.CalledProcessError):
            self.registry.create_worktree("project-two", "not-git")

    def test_dirty_base_creates_clean_snapshot_and_integrates_only_after_base_is_clean(self):
        self._init_repo(self.project_root)
        self.registry.register("project-two", "Project Two", self.project_root)
        base_head = self._git(self.project_root, "rev-parse", "HEAD")
        (self.project_root / "base.txt").write_text("private local edit\n", encoding="utf-8")
        (self.project_root / "untracked.txt").write_text("untracked local work\n", encoding="utf-8")
        status_before = self._git(self.project_root, "status", "--porcelain")

        created = self.registry.create_worktree("project-two", "dirty-snapshot")

        mission_root = Path(created["root"])
        self.assertTrue(created["metadata"]["base_dirty_at_creation"])
        self.assertEqual(created["base_branch"], "main")
        self.assertEqual(created["base_head"], base_head)
        self.assertEqual(self._git(mission_root, "rev-parse", "HEAD"), base_head)
        self.assertEqual(self._git(mission_root, "status", "--porcelain"), "")
        self.assertEqual((mission_root / "base.txt").read_text(encoding="utf-8"), "base\n")

        # Worktree creation must not stage, discard, copy, or otherwise mutate
        # anything in the user's dirty checkout.
        self.assertEqual((self.project_root / "base.txt").read_text(encoding="utf-8"), "private local edit\n")
        self.assertEqual((self.project_root / "untracked.txt").read_text(encoding="utf-8"), "untracked local work\n")
        self.assertEqual(self._git(self.project_root, "status", "--porcelain"), status_before)
        self.assertEqual(self._git(self.project_root, "rev-parse", "HEAD"), base_head)

        (mission_root / "mission.txt").write_text("isolated result\n", encoding="utf-8")
        self.registry.commit_worktree("project-two", "dirty-snapshot", "isolated mission")

        # Integration remains fail-closed while any local change is present.
        with self.assertRaises(RuntimeError):
            self.registry.integrate_worktree("project-two", "dirty-snapshot", "ff-only")
        self.assertFalse((self.project_root / "mission.txt").exists())

        # Once the disposable test checkout is clean and still on the recorded
        # branch/HEAD, the isolated commit can be integrated normally.
        self._git(self.project_root, "restore", "base.txt")
        (self.project_root / "untracked.txt").unlink()
        self.assertEqual(self._git(self.project_root, "status", "--porcelain"), "")
        integrated = self.registry.integrate_worktree("project-two", "dirty-snapshot", "ff-only")

        self.assertEqual(integrated["status"], "integrated")
        self.assertEqual((self.project_root / "mission.txt").read_text(encoding="utf-8"), "isolated result\n")
        self.registry.cleanup_worktree("project-two", "dirty-snapshot")

    def test_integration_rejects_moved_or_dirty_base(self):
        self._init_repo(self.project_root)
        self.registry.register("project-two", "Project Two", self.project_root)
        created = self.registry.create_worktree("project-two", "strict-base")
        (Path(created["root"]) / "mission.txt").write_text("mission\n", encoding="utf-8")
        self.registry.commit_worktree("project-two", "strict-base", "mission")
        (self.project_root / "local.txt").write_text("local change\n", encoding="utf-8")

        with self.assertRaises(RuntimeError):
            self.registry.integrate_worktree("project-two", "strict-base")

        (self.project_root / "local.txt").unlink()
        # Preserve the committed mission branch for inspection; cleanup correctly
        # refuses to destroy an unintegrated commit.
        with self.assertRaises(RuntimeError):
            self.registry.cleanup_worktree("project-two", "strict-base")
        # Explicitly integrate so normal cleanup can release the disposable tree.
        self.registry.integrate_worktree("project-two", "strict-base", "ff-only")
        self.registry.cleanup_worktree("project-two", "strict-base")

    def test_integration_rejects_clean_base_when_recorded_head_moved(self):
        self._init_repo(self.project_root)
        self.registry.register("project-two", "Project Two", self.project_root)
        created = self.registry.create_worktree("project-two", "moved-base")
        (Path(created["root"]) / "mission.txt").write_text("mission\n", encoding="utf-8")
        self.registry.commit_worktree("project-two", "moved-base", "mission")

        (self.project_root / "new-base.txt").write_text("new base commit\n", encoding="utf-8")
        self._git(self.project_root, "add", "new-base.txt")
        self._git(self.project_root, "commit", "-m", "move base")
        self.assertEqual(self._git(self.project_root, "status", "--porcelain"), "")

        with self.assertRaisesRegex(RuntimeError, "Base branch or HEAD moved"):
            self.registry.integrate_worktree("project-two", "moved-base", "ff-only")
        self.assertFalse((self.project_root / "mission.txt").exists())


if __name__ == "__main__":
    unittest.main()
