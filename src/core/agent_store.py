"""Durable SQLite storage for autonomous JARVIS runs and schedules."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


SENSITIVE_FIELD_PATTERN = re.compile(
    r"^(?:token|(?:(?:[a-z0-9]+)[_.-])*(?:api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|authorization|password|passwd|secret|credential|cookie|"
    r"session[_-]?token|private[_-]?key|client[_-]?secret|database[_-]?url|"
    r"db[_-]?(?:url|pass|password)|smtp[_-]?(?:pass|password)|dsn|"
    r"connection[_-]?string)(?:(?:[_.-])[a-z0-9]+)*)$",
    flags=re.IGNORECASE,
)
_SAFE_REFERENCE_FIELD_PATTERN = re.compile(
    r"(?:credential|secret|capability)[_.-]?(?:ref|reference)$",
    flags=re.IGNORECASE,
)
_SAFE_REFERENCE_VALUE_PATTERN = re.compile(
    r"^(?:credential|secret|capability)(?:://|:)[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$",
    flags=re.IGNORECASE,
)


def _is_safe_reference(field_name: str, value: Any) -> bool:
    return bool(
        _SAFE_REFERENCE_FIELD_PATTERN.search(field_name)
        and isinstance(value, str)
        and _SAFE_REFERENCE_VALUE_PATTERN.fullmatch(value)
    )


def _redacted_summary(value: Any) -> str:
    """Return a constant marker with no secret-derived fingerprint or length."""
    return "[REDACTED_CREDENTIAL]"


def redact_sensitive_text(value: str) -> str:
    """Redact credential-shaped text, credentialed URIs, and signed URLs."""
    redacted = re.sub(
        r"\bnvapi-[A-Za-z0-9_-]{12,}\b",
        "nvapi-[REDACTED]",
        value,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
        r"sk-[A-Za-z0-9_-]{20,})\b",
        "[REDACTED_CREDENTIAL]",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(?i)\b((?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]{12,}",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        "[REDACTED_JWT]",
        redacted,
    )
    # URI userinfo is always treated as a credential, including database DSNs.
    redacted = re.sub(
        r"(?i)\b([a-z][a-z0-9+.-]*://)([^/@\s:]+):([^/@\s]+)@",
        r"\1[REDACTED]@",
        redacted,
    )
    signed_query_names = (
        r"x-amz-(?:signature|credential|security-token)|x-goog-(?:signature|credential)|"
        r"signature|sig|access_token|refresh_token|api[_-]?key|token"
    )
    redacted = re.sub(
        rf"(?i)([?&](?:{signed_query_names})=)[^&#\s]+",
        r"\1[REDACTED]",
        redacted,
    )
    assignment = re.compile(
        r"(?im)\b([A-Z0-9_.-]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|REFRESH[_-]?TOKEN|"
        r"PASSWORD|PASSWD|SECRET|CREDENTIAL|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET|"
        r"DATABASE[_-]?URL|DB[_-]?(?:URL|PASS|PASSWORD)|SMTP[_-]?(?:PASS|PASSWORD)|"
        r"CONNECTION[_-]?STRING|DSN)[A-Z0-9_.-]*\s*(?::(?!//)|=)\s*)"
        r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"
    )
    redacted = assignment.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    # `token` is also a credential field by itself. Keep this separate from the
    # composite-field expression above so telemetry such as `token_count=42`
    # remains intact.
    exact_token_assignment = re.compile(
        r"(?im)\b(TOKEN\s*(?::(?!//)|=)\s*)"
        r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"
    )
    redacted = exact_token_assignment.sub(
        lambda match: f"{match.group(1)}[REDACTED]", redacted,
    )
    redacted = re.sub(
        r"(?is)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "[REDACTED_PRIVATE_KEY]",
        redacted,
    )
    return redacted


def contains_sensitive_data(value: Any, *, field_name: str | None = None) -> bool:
    """Conservatively identify data that must not enter prompts or durable payloads."""
    if field_name and SENSITIVE_FIELD_PATTERN.fullmatch(field_name):
        return not _is_safe_reference(field_name, value)
    if isinstance(value, dict):
        return any(
            contains_sensitive_data(item, field_name=str(key))
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return any(contains_sensitive_data(item) for item in value)
    if isinstance(value, str):
        return redact_sensitive_text(value) != value
    return False


def sanitize_for_storage(value: Any, *, field_name: str | None = None) -> Any:
    """Create a JSON-safe public/durable projection with no raw credentials."""
    if field_name and SENSITIVE_FIELD_PATTERN.fullmatch(field_name):
        return value if _is_safe_reference(field_name, value) else _redacted_summary(value)
    if isinstance(value, dict):
        return {
            str(key): sanitize_for_storage(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value


def sanitize_run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a run and retain which planned actions lost executable secrets."""
    redacted_steps = {
        int(index) for index in payload.get("redacted_step_indices", [])
        if isinstance(index, int) or (isinstance(index, str) and index.isdigit())
    }
    plan = payload.get("plan")
    if isinstance(plan, dict) and isinstance(plan.get("steps"), list):
        for index, step in enumerate(plan["steps"]):
            if isinstance(step, dict) and contains_sensitive_data(step):
                redacted_steps.add(index)
    goal_redacted = bool(payload.get("redacted_goal")) or contains_sensitive_data(
        payload.get("goal", "")
    )
    secret_bearing = bool(redacted_steps or goal_redacted)
    unsafe_action_digests: set[str] = set()

    def collect_action_digests(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "action_digest" and isinstance(item, str):
                    unsafe_action_digests.add(item)
                collect_action_digests(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                collect_action_digests(item)

    if secret_bearing:
        collect_action_digests(payload)

    sanitized = sanitize_for_storage(payload)
    if not isinstance(sanitized, dict):  # Defensive type narrowing.
        raise TypeError("agent run payload must be a mapping")

    if secret_bearing:
        marker = "0" * 64

        def replace_action_digests(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key: (
                        marker
                        if key == "action_digest"
                        else replace_action_digests(item)
                    )
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [replace_action_digests(item) for item in value]
            if isinstance(value, str):
                for digest in unsafe_action_digests:
                    if digest and digest in value:
                        value = value.replace(digest, marker)
                return value
            return value

        sanitized = replace_action_digests(sanitized)
        # A sanitized challenge or in-flight receipt can no longer identify the
        # exact effect that was approved or started. Do not retain executable
        # authority after credential material has been removed.
        sanitized["pending_approval"] = None
        sanitized["in_flight_effect"] = None
        sanitized["approved_steps"] = []
        if sanitized.get("status") not in {
            "completed", "failed", "cancelled", "needs_attention",
        }:
            sanitized["status"] = "needs_attention"
            sanitized["error"] = "secret_reentry_required"
    sanitized["redacted_step_indices"] = sorted(redacted_steps)
    sanitized["redacted_goal"] = goal_redacted
    return sanitized


def sanitize_schedule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a schedule; legacy credential-bearing goals are disabled."""
    goal_redacted = bool(payload.get("redacted_goal")) or contains_sensitive_data(
        payload.get("goal", "")
    )
    sanitized = sanitize_for_storage(payload)
    if not isinstance(sanitized, dict):
        raise TypeError("agent schedule payload must be a mapping")
    sanitized["redacted_goal"] = goal_redacted
    if goal_redacted:
        sanitized["enabled"] = False
    return sanitized


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
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_approval_claims (
                    run_id TEXT NOT NULL,
                    challenge_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    action_digest TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    PRIMARY KEY(run_id, challenge_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_run_leases (
                    run_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_schedule_occurrences (
                    schedule_id TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    PRIMARY KEY(schedule_id, due_at),
                    UNIQUE(run_id)
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_updated ON agent_runs(updated_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_agent_schedules_next ON agent_schedules(enabled, next_run_at)")
            self._sanitize_existing_payloads(connection)

    @staticmethod
    def _sanitize_existing_payloads(connection: sqlite3.Connection) -> None:
        for table, sanitizer in (
            ("agent_runs", sanitize_run_payload),
            ("agent_schedules", sanitize_schedule_payload),
        ):
            rows = connection.execute(f"SELECT id, payload FROM {table}").fetchall()
            for row in rows:
                try:
                    original = json.loads(row["payload"])
                    sanitized = sanitizer(original)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                encoded = json.dumps(sanitized, ensure_ascii=False)
                if table == "agent_runs" and (
                    sanitized.get("redacted_goal")
                    or sanitized.get("redacted_step_indices")
                ):
                    # Claims and leases are effect authority, not audit history. A
                    # digest derived from removed credentials cannot remain usable.
                    connection.execute(
                        "DELETE FROM agent_approval_claims WHERE run_id = ?", (row["id"],),
                    )
                    connection.execute(
                        "DELETE FROM agent_run_leases WHERE run_id = ?", (row["id"],),
                    )
                if encoded != row["payload"]:
                    if table == "agent_runs":
                        connection.execute(
                            "UPDATE agent_runs SET status = ?, payload = ? WHERE id = ?",
                            (sanitized.get("status", "needs_attention"), encoded, row["id"]),
                        )
                    else:
                        connection.execute(
                            "UPDATE agent_schedules SET enabled = ?, payload = ? WHERE id = ?",
                            (int(sanitized.get("enabled", False)), encoded, row["id"]),
                        )

    def save_run(self, payload: dict[str, Any], *, owner_id: str | None = None) -> bool:
        payload = sanitize_run_payload(payload)
        encoded = json.dumps(payload, ensure_ascii=False)
        unsafe_authority = bool(
            payload.get("redacted_goal") or payload.get("redacted_step_indices")
        )
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if unsafe_authority:
                connection.execute(
                    "DELETE FROM agent_approval_claims WHERE run_id = ?", (payload["id"],),
                )
                connection.execute(
                    "DELETE FROM agent_run_leases WHERE run_id = ?", (payload["id"],),
                )
            lease = connection.execute(
                "SELECT owner_id, expires_at FROM agent_run_leases WHERE run_id = ?",
                (payload["id"],),
            ).fetchone()
            if (
                lease is not None
                and lease["expires_at"] > datetime.now().isoformat()
                and lease["owner_id"] != owner_id
            ):
                return False
            connection.execute(
                """INSERT INTO agent_runs(id, status, created_at, updated_at, payload)
                   VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     status=excluded.status, updated_at=excluded.updated_at, payload=excluded.payload""",
                (payload["id"], payload["status"], payload["created_at"], payload["updated_at"], encoded),
            )
            return True

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return sanitize_run_payload(json.loads(row["payload"])) if row else None

    def load_runs(self, limit: int = 250) -> list[dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM agent_runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [sanitize_run_payload(json.loads(row["payload"])) for row in rows]

    @staticmethod
    def _current_action(payload: dict[str, Any]) -> dict[str, Any] | None:
        plan = payload.get("plan")
        index = payload.get("current_step")
        if not isinstance(plan, dict) or not isinstance(index, int):
            return None
        steps = plan.get("steps")
        if not isinstance(steps, list) or index < 0 or index >= len(steps):
            return None
        step = steps[index]
        return step if isinstance(step, dict) else None

    def claim_approval(
        self,
        payload: dict[str, Any],
        *,
        challenge_id: str,
        step_id: str,
        action_digest: str,
        claimed_at: str,
        owner_id: str,
        lease_expires_at: str,
    ) -> bool:
        """Atomically consume the exact durable challenge and acquire execution."""
        payload = sanitize_run_payload(payload)
        encoded = json.dumps(payload, ensure_ascii=False)
        run_id = str(payload["id"])
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return False
            current = sanitize_run_payload(json.loads(row["payload"]))
            pending = current.get("pending_approval")
            next_pending = payload.get("pending_approval")
            if not isinstance(pending, dict) or not isinstance(next_pending, dict):
                return False
            try:
                durable_expiry = datetime.fromisoformat(
                    str(pending.get("expires_at", "")).replace("Z", "+00:00")
                )
                durable_issued = datetime.fromisoformat(
                    str(pending.get("issued_at", "")).replace("Z", "+00:00")
                )
                claim_time = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
                invalid_durable_window = (
                    durable_expiry <= claim_time or durable_issued >= durable_expiry
                )
            except (TypeError, ValueError):
                return False
            if (
                current.get("status") != "awaiting_confirmation"
                or pending.get("challenge_id") != challenge_id
                or pending.get("step_id") != step_id
                or pending.get("action_digest") != action_digest
                or pending.get("approved_at") is not None
                or next_pending.get("challenge_id") != challenge_id
                or next_pending.get("step_id") != step_id
                or next_pending.get("action_digest") != action_digest
                or next_pending.get("issued_at") != pending.get("issued_at")
                or next_pending.get("expires_at") != pending.get("expires_at")
                or next_pending.get("approved_at") != claimed_at
                or invalid_durable_window
                or current.get("current_step") != payload.get("current_step")
                or current.get("workspace_root") != payload.get("workspace_root")
                or self._current_action(current) != self._current_action(payload)
            ):
                return False
            lease = connection.execute(
                "SELECT owner_id, expires_at FROM agent_run_leases WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if lease is not None and lease["owner_id"] != owner_id and lease["expires_at"] > claimed_at:
                return False
            inserted = connection.execute(
                """INSERT OR IGNORE INTO agent_approval_claims(
                       run_id, challenge_id, step_id, action_digest, claimed_at
                   ) VALUES(?, ?, ?, ?, ?)""",
                (run_id, challenge_id, step_id, action_digest, claimed_at),
            )
            if inserted.rowcount != 1:
                return False
            connection.execute(
                """INSERT INTO agent_run_leases(
                       run_id, owner_id, acquired_at, heartbeat_at, expires_at
                   ) VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(run_id) DO UPDATE SET owner_id=excluded.owner_id,
                     acquired_at=excluded.acquired_at, heartbeat_at=excluded.heartbeat_at,
                     expires_at=excluded.expires_at""",
                (run_id, owner_id, claimed_at, claimed_at, lease_expires_at),
            )
            connection.execute(
                "UPDATE agent_runs SET status = ?, updated_at = ?, payload = ? WHERE id = ?",
                (payload["status"], payload["updated_at"], encoded, run_id),
            )
            return True

    def claim_run_execution(
        self,
        run_id: str,
        *,
        owner_id: str,
        claimed_at: str,
        lease_expires_at: str,
    ) -> bool:
        """Acquire an unambiguous execution lease across runtimes/processes."""
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return False
            payload = sanitize_run_payload(json.loads(row["payload"]))
            if payload.get("status") not in {"queued", "planning", "running", "synthesizing"}:
                return False
            if payload.get("in_flight_effect") is not None:
                return False
            lease = connection.execute(
                "SELECT owner_id, expires_at FROM agent_run_leases WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if lease is not None and lease["owner_id"] != owner_id and lease["expires_at"] > claimed_at:
                return False
            connection.execute(
                """INSERT INTO agent_run_leases(
                       run_id, owner_id, acquired_at, heartbeat_at, expires_at
                   ) VALUES(?, ?, ?, ?, ?)
                   ON CONFLICT(run_id) DO UPDATE SET owner_id=excluded.owner_id,
                     acquired_at=excluded.acquired_at, heartbeat_at=excluded.heartbeat_at,
                     expires_at=excluded.expires_at""",
                (run_id, owner_id, claimed_at, claimed_at, lease_expires_at),
            )
            return True

    def renew_run_execution(
        self, run_id: str, *, owner_id: str, heartbeat_at: str, lease_expires_at: str,
    ) -> bool:
        with self._lock, self._connection() as connection:
            updated = connection.execute(
                """UPDATE agent_run_leases
                   SET heartbeat_at = ?, expires_at = ?
                   WHERE run_id = ? AND owner_id = ?""",
                (heartbeat_at, lease_expires_at, run_id, owner_id),
            )
        return updated.rowcount == 1

    def release_run_execution(self, run_id: str, *, owner_id: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                "DELETE FROM agent_run_leases WHERE run_id = ? AND owner_id = ?",
                (run_id, owner_id),
            )

    def run_has_live_execution_claim(self, run_id: str, *, now: str) -> bool:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM agent_run_leases WHERE run_id = ? AND expires_at > ?",
                (run_id, now),
            ).fetchone()
        return row is not None

    def mark_effect_needs_attention(
        self,
        payload: dict[str, Any],
        *,
        step_index: int,
        action_digest: str,
    ) -> bool:
        """Fail safe if an effect returns after its execution lease was lost."""
        payload = sanitize_run_payload(payload)
        encoded = json.dumps(payload, ensure_ascii=False)
        run_id = str(payload["id"])
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return False
            current = sanitize_run_payload(json.loads(row["payload"]))
            receipt = current.get("in_flight_effect")
            if not isinstance(receipt, dict):
                return False
            if (
                receipt.get("step_index") != step_index
                or receipt.get("action_digest") != action_digest
                or payload.get("status") != "needs_attention"
                or payload.get("in_flight_effect") is None
            ):
                return False
            connection.execute(
                "UPDATE agent_runs SET status = ?, updated_at = ?, payload = ? WHERE id = ?",
                (payload["status"], payload["updated_at"], encoded, run_id),
            )
            return True

    def save_schedule(self, payload: dict[str, Any]) -> None:
        payload = sanitize_schedule_payload(payload)
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
        return [sanitize_schedule_payload(json.loads(row["payload"])) for row in rows]

    def claim_schedule_occurrence(
        self,
        *,
        schedule_id: str,
        due_at: str,
        schedule_payload: dict[str, Any],
        run_payload: dict[str, Any],
        claimed_at: str,
    ) -> bool:
        """Create one due run and advance its schedule in one durable transaction."""
        schedule_payload = sanitize_schedule_payload(schedule_payload)
        run_payload = sanitize_run_payload(run_payload)
        encoded_schedule = json.dumps(schedule_payload, ensure_ascii=False)
        encoded_run = json.dumps(run_payload, ensure_ascii=False)
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM agent_schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
            if row is None:
                return False
            current = sanitize_schedule_payload(json.loads(row["payload"]))
            if not current.get("enabled", True) or current.get("next_run_at") != due_at:
                return False
            inserted = connection.execute(
                """INSERT OR IGNORE INTO agent_schedule_occurrences(
                       schedule_id, due_at, run_id, claimed_at
                   ) VALUES(?, ?, ?, ?)""",
                (schedule_id, due_at, run_payload["id"], claimed_at),
            )
            if inserted.rowcount != 1:
                return False
            connection.execute(
                """INSERT INTO agent_runs(id, status, created_at, updated_at, payload)
                   VALUES(?, ?, ?, ?, ?)""",
                (
                    run_payload["id"], run_payload["status"], run_payload["created_at"],
                    run_payload["updated_at"], encoded_run,
                ),
            )
            connection.execute(
                """UPDATE agent_schedules
                   SET enabled = ?, next_run_at = ?, interval_seconds = ?,
                       payload = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    int(schedule_payload.get("enabled", True)),
                    schedule_payload["next_run_at"],
                    schedule_payload.get("interval_seconds"),
                    encoded_schedule,
                    schedule_payload["updated_at"],
                    schedule_id,
                ),
            )
            return True

    def load_schedule_occurrence_run(
        self, *, schedule_id: str, due_at: str,
    ) -> dict[str, Any] | None:
        """Load the run already committed for one exact schedule occurrence."""
        with self._lock, self._connection() as connection:
            row = connection.execute(
                """SELECT run.payload
                   FROM agent_schedule_occurrences AS occurrence
                   JOIN agent_runs AS run ON run.id = occurrence.run_id
                   WHERE occurrence.schedule_id = ? AND occurrence.due_at = ?""",
                (schedule_id, due_at),
            ).fetchone()
        if row is None:
            return None
        return sanitize_run_payload(json.loads(row["payload"]))

    def delete_schedule(self, schedule_id: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute("DELETE FROM agent_schedules WHERE id = ?", (schedule_id,))
