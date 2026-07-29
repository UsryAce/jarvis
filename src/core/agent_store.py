"""Durable SQLite storage for autonomous JARVIS runs and schedules."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class AgentStore:
    """Small synchronous store; operations are short and protected by a lock."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
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
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_schedules (
                    id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    next_run_at TEXT NOT NULL,
                    interval_seconds INTEGER,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_updated ON agent_runs(updated_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_agent_schedules_next ON agent_schedules(enabled, next_run_at)")

    def save_run(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO agent_runs(id, status, created_at, updated_at, payload)
                   VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     status=excluded.status, updated_at=excluded.updated_at, payload=excluded.payload""",
                (payload["id"], payload["status"], payload["created_at"], payload["updated_at"], encoded),
            )

    def load_runs(self, limit: int = 250) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM agent_runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def save_schedule(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO agent_schedules(id, enabled, next_run_at, interval_seconds, payload, created_at, updated_at)
                   VALUES(?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,
                     next_run_at=excluded.next_run_at, interval_seconds=excluded.interval_seconds,
                     payload=excluded.payload, updated_at=excluded.updated_at""",
                (
                    payload["id"], int(payload.get("enabled", True)), payload["next_run_at"],
                    payload.get("interval_seconds"), encoded, payload["created_at"], payload["updated_at"],
                ),
            )

    def load_schedules(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute("SELECT payload FROM agent_schedules ORDER BY next_run_at").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def delete_schedule(self, schedule_id: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute("DELETE FROM agent_schedules WHERE id = ?", (schedule_id,))
