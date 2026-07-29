"""Persistent, user-scoped project workspace registry for JARVIS agents."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class WorkspaceRegistry:
    def __init__(self, database: Path, default_root: Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.default_root = Path(default_root).resolve()
        self.allowed_root = Path.home().resolve()
        self.worktree_root = (self.database.parent / ".jarvis-worktrees").resolve()
        self._assert_inside(self.worktree_root, self.allowed_root)
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()
        self.register("jarvis", "JARVIS", self.default_root, protected=True)

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=15000")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root TEXT NOT NULL UNIQUE,
                    protected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS mission_worktrees (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    root TEXT NOT NULL UNIQUE,
                    branch TEXT NOT NULL UNIQUE,
                    base_root TEXT NOT NULL,
                    base_branch TEXT NOT NULL,
                    base_head TEXT NOT NULL,
                    commit_head TEXT,
                    integrated_head TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY(project_id, run_id),
                    FOREIGN KEY(project_id) REFERENCES project_workspaces(id)
                )"""
            )

    def register(
        self, project_id: str, name: str, root: str | Path,
        protected: bool = False, metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        identifier = self._identifier(project_id)
        resolved = Path(root).expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError("Project workspace must be an existing directory")
        try:
            resolved.relative_to(self.allowed_root)
        except ValueError as exc:
            raise PermissionError(f"Project workspace must stay inside {self.allowed_root}") from exc
        now = datetime.now().isoformat()
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO project_workspaces(id, name, root, protected, created_at, updated_at, metadata)
                   VALUES(?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, root=excluded.root,
                     protected=MAX(project_workspaces.protected, excluded.protected),
                     updated_at=excluded.updated_at, metadata=excluded.metadata""",
                (identifier, name.strip() or identifier, str(resolved), int(protected), now, now, json.dumps(metadata or {})),
            )
        return self.get(identifier)

    def get(self, project_id: str) -> dict[str, Any]:
        identifier = self._identifier(project_id)
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT * FROM project_workspaces WHERE id = ?", (identifier,)).fetchone()
        if not row:
            raise KeyError(identifier)
        return self._decorate(dict(row))

    def resolve(self, project_id: str) -> Path:
        if project_id in {"", "default"}:
            project_id = "jarvis"
        return Path(self.get(project_id)["root"])

    def list(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute("SELECT * FROM project_workspaces ORDER BY protected DESC, name").fetchall()
        return [self._decorate(dict(row)) for row in rows]

    def remove(self, project_id: str) -> None:
        project = self.get(project_id)
        if project["protected"]:
            raise PermissionError("The default JARVIS workspace cannot be removed")
        with self._lock, self._connection() as connection:
            active = connection.execute(
                "SELECT 1 FROM mission_worktrees WHERE project_id = ? AND status != 'cleaned' LIMIT 1",
                (project["id"],),
            ).fetchone()
            if active:
                raise RuntimeError("Clean up active mission worktrees before removing the project")
            connection.execute("DELETE FROM project_workspaces WHERE id = ?", (project["id"],))

    def create_worktree(self, project_id: str, run_id: str) -> dict[str, Any]:
        """Create (or recover) one clean, isolated Git worktree for a mission."""
        project = self.get(project_id)
        project_id = project["id"]
        run_id = self._identifier(run_id)
        with self._lock:
            existing = self._find_worktree(project_id, run_id)
            if existing:
                if existing["status"] != "cleaned" and Path(existing["root"]).is_dir():
                    return self._decorate_worktree(existing)
                return self._decorate_worktree(existing)

            base_root = Path(project["root"]).resolve()
            # A dirty user checkout is safe as a *source* for a mission worktree:
            # Git materializes the new tree from the recorded commit, not from the
            # checkout's index or working-tree contents.  Keep integration strict,
            # but do not make unrelated local edits block isolated agent work.
            status = self._inspect_git_base(base_root)
            branch = f"jarvis/{run_id}"
            path = (self.worktree_root / project_id / run_id).resolve()
            self._assert_inside(path, self.worktree_root)
            branch_exists = self._git(
                base_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False,
            ).returncode == 0
            if branch_exists and path.is_dir():
                # Recover the narrow crash window after `git worktree add` and before
                # the SQLite insert. Both the managed path and exact branch must match.
                recovered_top = Path(self._git(path, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
                recovered_branch = self._git(path, "branch", "--show-current").stdout.strip()
                if recovered_top == path and recovered_branch == branch:
                    return self._persist_recovered_worktree(
                        project_id, run_id, path, branch, base_root, status,
                    )
                raise FileExistsError(f"Unmanaged path or branch occupies {path}")
            if branch_exists:
                raise ValueError(f"Mission branch already exists: {branch}")
            if path.exists():
                raise FileExistsError(f"Unmanaged worktree path already exists: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            self._git(base_root, "worktree", "add", "-b", branch, str(path), status["head"])
            now = datetime.now().isoformat()
            try:
                with self._connection() as connection:
                    connection.execute(
                        """INSERT INTO mission_worktrees(
                             project_id, run_id, root, branch, base_root, base_branch, base_head,
                             commit_head, integrated_head, status, created_at, updated_at, metadata
                           ) VALUES(?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'active', ?, ?, ?)""",
                        (project_id, run_id, str(path), branch, str(base_root), status["branch"],
                         status["head"], now, now,
                         json.dumps({"base_dirty_at_creation": status["dirty"]})),
                    )
            except Exception:
                # The Git operation succeeded but persistence failed. A normal, non-forced
                # removal is safe because the newly-created tree is still clean.
                self._git(base_root, "worktree", "remove", str(path), check=False)
                self._git(base_root, "branch", "-d", branch, check=False)
                raise
        return self.get_worktree(project_id, run_id)

    def get_worktree(self, project_id: str, run_id: str) -> dict[str, Any]:
        project_id = self._identifier(project_id)
        run_id = self._identifier(run_id)
        row = self._find_worktree(project_id, run_id)
        if not row:
            raise KeyError(f"{project_id}/{run_id}")
        return self._decorate_worktree(row)

    def list_worktrees(self, project_id: str | None = None) -> list[dict[str, Any]]:
        params: tuple[str, ...] = ()
        query = "SELECT * FROM mission_worktrees"
        if project_id is not None:
            query += " WHERE project_id = ?"
            params = (self._identifier(project_id),)
        query += " ORDER BY created_at DESC"
        with self._lock, self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._decorate_worktree(dict(row)) for row in rows]

    def inspect_worktree(self, project_id: str, run_id: str) -> dict[str, Any]:
        record = self.get_worktree(project_id, run_id)
        if record["status"] == "cleaned" or not Path(record["root"]).is_dir():
            return {**record, "changed_files": [], "diff_stat": "", "ahead": 0, "clean": True}
        root = Path(record["root"])
        porcelain = self._git(root, "status", "--porcelain").stdout
        changed = [line[3:] for line in porcelain.splitlines() if len(line) > 3]
        diff_stat = self._git(root, "diff", "--stat", record["base_head"], "--").stdout.strip()
        ahead_raw = self._git(root, "rev-list", "--count", f'{record["base_head"]}..HEAD').stdout.strip()
        return {
            **record,
            "changed_files": changed,
            "diff_stat": diff_stat,
            "ahead": int(ahead_raw or "0"),
            "clean": not bool(porcelain.strip()),
            "head": self._git(root, "rev-parse", "HEAD").stdout.strip(),
        }

    def commit_worktree(
        self, project_id: str, run_id: str, message: str,
        author_name: str = "JARVIS", author_email: str = "jarvis@localhost",
    ) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("Commit message cannot be empty")
        with self._lock:
            record = self.get_worktree(project_id, run_id)
            if record["status"] in {"integrated", "cleaned"}:
                return self.inspect_worktree(project_id, run_id)
            root = self._active_worktree_path(record)
            if not self._git(root, "status", "--porcelain").stdout.strip():
                head = self._git(root, "rev-parse", "HEAD").stdout.strip()
                if head != record["base_head"] and record["commit_head"] != head:
                    # Recover a commit that completed just before persistence.
                    self._update_worktree(project_id, run_id, commit_head=head, status="committed")
                return self.inspect_worktree(project_id, run_id)
            self._git(root, "add", "--all")
            self._git(
                root, "-c", f"user.name={author_name}", "-c", f"user.email={author_email}",
                "commit", "-m", message.strip(),
            )
            head = self._git(root, "rev-parse", "HEAD").stdout.strip()
            self._update_worktree(project_id, run_id, commit_head=head, status="committed")
        return self.inspect_worktree(project_id, run_id)

    def integrate_worktree(
        self, project_id: str, run_id: str, strategy: str = "cherry-pick",
    ) -> dict[str, Any]:
        """Integrate a clean mission tree only if its base branch has not moved."""
        if strategy not in {"cherry-pick", "ff-only", "merge"}:
            raise ValueError("Integration strategy must be cherry-pick, ff-only, or merge")
        with self._lock:
            record = self.get_worktree(project_id, run_id)
            if record["status"] in {"integrated", "cleaned"}:
                return record
            root = self._active_worktree_path(record)
            if self._git(root, "status", "--porcelain").stdout.strip():
                raise RuntimeError("Commit or discard mission changes before integration")
            base = Path(record["base_root"])
            current = self._require_clean_git_base(base)
            head = self._git(root, "rev-parse", "HEAD").stdout.strip()
            if (current["branch"] == record["base_branch"] and
                    current["head"] != record["base_head"] and
                    self._git(base, "diff", "--quiet", current["head"], head, check=False).returncode == 0):
                # Recover integration that changed Git successfully but was interrupted
                # before its SQLite status update. Exact resulting trees must match.
                self._update_worktree(project_id, run_id, commit_head=head,
                                      integrated_head=current["head"], status="integrated")
                return self.get_worktree(project_id, run_id)
            if current["branch"] != record["base_branch"] or current["head"] != record["base_head"]:
                raise RuntimeError("Base branch or HEAD moved since mission creation; refusing integration")
            if self._git(root, "merge-base", "--is-ancestor", record["base_head"], head, check=False).returncode != 0:
                raise RuntimeError("Mission history is not descended from its recorded base")
            if head != record["base_head"]:
                if strategy == "cherry-pick":
                    commits = self._git(root, "rev-list", "--reverse", f'{record["base_head"]}..{head}').stdout.split()
                    try:
                        self._git(base, "cherry-pick", *commits)
                    except subprocess.CalledProcessError:
                        self._git(base, "cherry-pick", "--abort", check=False)
                        raise
                else:
                    # With an unchanged base, both supported merge modes are deliberately
                    # fast-forward-only; no surprise merge commit or conflict is possible.
                    self._git(base, "merge", "--ff-only", head)
            integrated_head = self._git(base, "rev-parse", "HEAD").stdout.strip()
            self._update_worktree(project_id, run_id, commit_head=head,
                                  integrated_head=integrated_head, status="integrated")
        return self.get_worktree(project_id, run_id)

    def cleanup_worktree(
        self, project_id: str, run_id: str, delete_branch: bool = True,
    ) -> dict[str, Any]:
        """Remove a clean integrated/empty worktree without force or data loss."""
        with self._lock:
            record = self.get_worktree(project_id, run_id)
            if record["status"] == "cleaned":
                return record
            if not Path(record["root"]).is_dir():
                if record["status"] != "integrated" and record["commit_head"]:
                    raise RuntimeError("Missing worktree still owns an unintegrated mission commit")
                base = Path(record["base_root"])
                branch_deleted = False
                if delete_branch:
                    result = self._git(base, "branch", "-d", record["branch"], check=False)
                    branch_deleted = result.returncode == 0
                self._update_worktree(project_id, run_id, status="cleaned",
                                      metadata={"branch_deleted": branch_deleted, "recovered": True})
                return self.get_worktree(project_id, run_id)
            root = self._active_worktree_path(record)
            if self._git(root, "status", "--porcelain").stdout.strip():
                raise RuntimeError("Refusing to remove a worktree with uncommitted changes")
            head = self._git(root, "rev-parse", "HEAD").stdout.strip()
            if record["status"] != "integrated" and head != record["base_head"]:
                raise RuntimeError("Refusing to remove an unintegrated mission commit")
            base = Path(record["base_root"])
            self._git(base, "worktree", "remove", str(root))
            branch_deleted = False
            if delete_branch:
                result = self._git(base, "branch", "-d", record["branch"], check=False)
                branch_deleted = result.returncode == 0
            self._update_worktree(project_id, run_id, status="cleaned",
                                  metadata={"branch_deleted": branch_deleted})
        return self.get_worktree(project_id, run_id)

    def _find_worktree(self, project_id: str, run_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM mission_worktrees WHERE project_id = ? AND run_id = ?",
                (project_id, run_id),
            ).fetchone()
        return dict(row) if row else None

    def _persist_recovered_worktree(
        self, project_id: str, run_id: str, path: Path, branch: str,
        base_root: Path, base_status: dict[str, Any],
    ) -> dict[str, Any]:
        head = self._git(path, "rev-parse", "HEAD").stdout.strip()
        if self._git(path, "merge-base", "--is-ancestor", base_status["head"], head, check=False).returncode != 0:
            raise RuntimeError("Recovered mission branch is not descended from the clean base")
        now = datetime.now().isoformat()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO mission_worktrees(
                     project_id, run_id, root, branch, base_root, base_branch, base_head,
                     commit_head, integrated_head, status, created_at, updated_at, metadata
                   ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)""",
                (project_id, run_id, str(path), branch, str(base_root), base_status["branch"],
                 base_status["head"], head if head != base_status["head"] else None,
                 "committed" if head != base_status["head"] else "active", now, now,
                 json.dumps({
                     "recovered": True,
                     "base_dirty_at_creation": bool(base_status["dirty"]),
                 })),
            )
        return self.get_worktree(project_id, run_id)

    def _update_worktree(self, project_id: str, run_id: str, **values: Any) -> None:
        allowed = {"commit_head", "integrated_head", "status", "metadata"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported worktree fields: {sorted(unknown)}")
        values["updated_at"] = datetime.now().isoformat()
        if "metadata" in values:
            values["metadata"] = json.dumps(values["metadata"])
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self._connection() as connection:
            connection.execute(
                f"UPDATE mission_worktrees SET {assignments} WHERE project_id = ? AND run_id = ?",
                (*values.values(), self._identifier(project_id), self._identifier(run_id)),
            )

    def _decorate_worktree(self, row: dict[str, Any]) -> dict[str, Any]:
        row["metadata"] = json.loads(row.get("metadata") or "{}")
        row["exists"] = Path(row["root"]).is_dir()
        return row

    def _active_worktree_path(self, record: dict[str, Any]) -> Path:
        root = Path(record["root"]).resolve()
        self._assert_inside(root, self.worktree_root)
        if not root.is_dir():
            raise FileNotFoundError(f"Mission worktree is missing: {root}")
        return root

    def _inspect_git_base(self, root: Path) -> dict[str, Any]:
        top = Path(self._git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
        if top != root.resolve():
            raise ValueError("Registered project root must be the Git repository root")
        branch = self._git(root, "branch", "--show-current").stdout.strip()
        if not branch:
            raise ValueError("Git project must be on a named branch")
        dirty = bool(self._git(root, "status", "--porcelain").stdout.strip())
        return {
            "branch": branch,
            "head": self._git(root, "rev-parse", "HEAD").stdout.strip(),
            "dirty": dirty,
        }

    def _require_clean_git_base(self, root: Path) -> dict[str, Any]:
        status = self._inspect_git_base(root)
        if status["dirty"]:
            raise RuntimeError("Git project must be clean before creating or integrating a mission")
        return status

    @staticmethod
    def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True,
                timeout=30, check=check,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise subprocess.CalledProcessError(
                exc.returncode, exc.cmd, output=exc.stdout, stderr=detail,
            ) from exc

    @staticmethod
    def _assert_inside(path: Path, parent: Path) -> None:
        try:
            path.resolve().relative_to(parent.resolve())
        except ValueError as exc:
            raise PermissionError(f"Path must stay inside {parent}") from exc

    def _decorate(self, row: dict[str, Any]) -> dict[str, Any]:
        root = Path(row["root"])
        row["protected"] = bool(row["protected"])
        row["metadata"] = json.loads(row.get("metadata") or "{}")
        row.update(self._git_status(root))
        return row

    @staticmethod
    def _git_status(root: Path) -> dict[str, Any]:
        try:
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"], cwd=root,
                capture_output=True, text=True, timeout=5, check=True,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=root,
                capture_output=True, text=True, timeout=5, check=False,
            ).stdout.strip()
            dirty = bool(subprocess.run(
                ["git", "status", "--porcelain"], cwd=root,
                capture_output=True, text=True, timeout=8, check=False,
            ).stdout.strip())
            return {"git": True, "git_root": top, "branch": branch or "detached", "dirty": dirty, "worktree_ready": not dirty}
        except (OSError, subprocess.SubprocessError):
            return {"git": False, "git_root": None, "branch": None, "dirty": False, "worktree_ready": False}

    @staticmethod
    def _identifier(value: str) -> str:
        identifier = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower()).strip("-")
        if not identifier or len(identifier) > 80:
            raise ValueError("Project id must contain 1-80 letters, numbers, underscores, or hyphens")
        return identifier
