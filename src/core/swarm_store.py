"""Durable SQLite storage for JARVIS multi-agent swarm runs."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class SwarmStore:
    """Thread-safe, compact persistence for swarm state and its event stream."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS swarm_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS swarm_tasks (
                    id TEXT PRIMARY KEY,
                    swarm_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(swarm_id) REFERENCES swarm_runs(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS swarm_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    swarm_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(swarm_id) REFERENCES swarm_runs(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_swarm_runs_updated
                    ON swarm_runs(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_swarm_tasks_run
                    ON swarm_tasks(swarm_id, status);
                CREATE INDEX IF NOT EXISTS idx_swarm_events_run
                    ON swarm_events(swarm_id, sequence);
                """
            )

    def save_run(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO swarm_runs(id, status, mode, project_id, created_at, updated_at, payload)
                   VALUES(?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                     mode=excluded.mode, project_id=excluded.project_id,
                     updated_at=excluded.updated_at, payload=excluded.payload""",
                (
                    payload["id"], payload["status"], payload["mode"],
                    payload["project_id"], payload["created_at"],
                    payload["updated_at"], encoded,
                ),
            )

    def save_task(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO swarm_tasks(id, swarm_id, status, role, created_at, updated_at, payload)
                   VALUES(?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                     role=excluded.role, updated_at=excluded.updated_at,
                     payload=excluded.payload""",
                (
                    payload["id"], payload["swarm_id"], payload["status"],
                    payload["role"], payload["created_at"],
                    payload["updated_at"], encoded,
                ),
            )

    def append_event(self, swarm_id: str, timestamp: str, event_type: str, payload: dict[str, Any]) -> int:
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO swarm_events(swarm_id, timestamp, event_type, payload) VALUES(?, ?, ?, ?)",
                (swarm_id, timestamp, event_type, encoded),
            )
            return int(cursor.lastrowid)

    def load_runs(self, limit: int = 250) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM swarm_runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def load_tasks(self, swarm_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM swarm_tasks WHERE swarm_id = ? ORDER BY created_at, id",
                (swarm_id,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def load_events(self, swarm_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """SELECT sequence, timestamp, event_type, payload FROM swarm_events
                   WHERE swarm_id = ? ORDER BY sequence DESC LIMIT ?""",
                (swarm_id, limit),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"], "timestamp": row["timestamp"],
                "event_type": row["event_type"], **json.loads(row["payload"]),
            }
            for row in reversed(rows)
        ]

    def load_unfinished(self) -> list[dict[str, Any]]:
        terminal = ("completed", "failed", "cancelled")
        placeholders = ",".join("?" for _ in terminal)
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                f"SELECT payload FROM swarm_runs WHERE status NOT IN ({placeholders}) ORDER BY created_at",
                terminal,
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]
