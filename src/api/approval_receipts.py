"""Safe, explicit receipts for non-atomic swarm approval operations."""

from __future__ import annotations

import uuid
from typing import Any, Iterable, Mapping
from urllib.parse import quote

from src.security.redaction import sanitize_text


APPROVAL_CONFLICT_DETAIL = "approval_challenge_conflict"
SWARM_RESUME_CONFLICT_DETAIL = "swarm_resume_conflict"
SWARM_APPROVAL_APPLIED_CODE = "swarm_approval_applied"
SWARM_APPROVAL_PARTIAL_CODE = "swarm_approval_partial"


def _safe_identifier(
    value: Any,
    *,
    fallback: str = "unknown",
    max_length: int = 128,
) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return sanitize_text(text, max_length=max_length)


def approval_applied_item(
    agent_run_id: str,
    step_id: str,
    approved_run: Any,
) -> dict[str, str]:
    """Project one completed child-approval call into a safe receipt item."""

    safe_agent_id = _safe_identifier(agent_run_id)
    safe_step_id = _safe_identifier(step_id)
    return {
        "id": _safe_identifier(
            f"{safe_agent_id}:{safe_step_id}", max_length=192,
        ),
        "agent_run_id": safe_agent_id,
        "step_id": safe_step_id,
        "status": _safe_identifier(getattr(approved_run, "status", None)),
    }


def _task_items(run: Any) -> Iterable[tuple[str, Any]]:
    tasks = getattr(run, "tasks", None)
    if isinstance(tasks, Mapping):
        return ((str(task_id), task) for task_id, task in tasks.items())
    if isinstance(tasks, list):
        return (
            (str(getattr(task, "id", index)), task)
            for index, task in enumerate(tasks)
        )
    return ()


def _authoritative_child_statuses(jarvis: Any, run: Any) -> list[dict[str, str]]:
    statuses: list[dict[str, str]] = []
    for task_id, task in _task_items(run):
        agent_run_id = str(getattr(task, "agent_run_id", None) or "").strip()
        agent_status = "unlinked"
        if agent_run_id:
            try:
                agent_run = jarvis.agent_runtime.get_run(agent_run_id)
            except Exception:  # Receipt generation must not mask the original conflict.
                agent_run = None
            agent_status = _safe_identifier(
                getattr(agent_run, "status", None), fallback="missing",
            )
        statuses.append({
            "task_id": _safe_identifier(task_id),
            "task_status": _safe_identifier(getattr(task, "status", None)),
            "agent_run_id": _safe_identifier(agent_run_id, fallback="unlinked"),
            "agent_status": agent_status,
        })
    return statuses


def swarm_approval_receipt(
    jarvis: Any,
    run_id: str,
    *,
    applied_items: list[dict[str, str]],
    requested_count: int,
    code: str,
    reason_code: str,
    ok: bool,
    resume_attempted: bool,
    failed_approval_id: str | None = None,
    resume_status: str | None = None,
    reconciliation_reason_code: str | None = None,
) -> dict[str, Any]:
    """Build a truth-preserving receipt without claiming approval atomicity."""

    try:
        run = jarvis.swarm_runtime.get_run(run_id)
    except Exception:  # Preserve the primary operation result even if refresh fails.
        run = None
    safe_run_id = _safe_identifier(run_id)
    swarm_status = _safe_identifier(getattr(run, "status", None), fallback="missing")
    applied_ids = [
        _safe_identifier(item.get("id"), max_length=192)
        for item in applied_items
    ]
    applied_count = len(applied_items)
    child_statuses = _authoritative_child_statuses(jarvis, run) if run else []
    needs_refresh = not ok
    guidance = (
        "One or more child approvals were applied. Refresh the swarm and linked "
        "agent runs before approving again; do not retry a stale challenge."
        if needs_refresh
        else "Approval state is authoritative for this response."
    )
    reconciliation: dict[str, Any] = {
        "required": needs_refresh,
        "action": "refresh_before_retry" if needs_refresh else "none",
        "guidance": guidance,
        "resume_attempted": resume_attempted,
        "resume_status": _safe_identifier(
            resume_status, fallback="not_attempted" if not resume_attempted else "unknown",
        ),
        "reason_code": (
            _safe_identifier(reconciliation_reason_code)
            if reconciliation_reason_code else None
        ),
        "swarm_status_endpoint": f"/api/swarm/runs/{quote(safe_run_id, safe='')}",
        "agent_status_endpoints": [
            f"/api/agent/runs/{quote(item['agent_run_id'], safe='')}"
            for item in applied_items
        ],
    }
    return {
        "ok": ok,
        "code": _safe_identifier(code),
        "correlation_id": str(uuid.uuid4()),
        "retryable": False,
        "applied": applied_count > 0,
        "partial": not ok and applied_count > 0,
        "applied_count": applied_count,
        "requested_count": max(0, int(requested_count)),
        "applied_ids": applied_ids,
        "applied_items": applied_items,
        "failed_approval_id": (
            _safe_identifier(failed_approval_id, max_length=192)
            if failed_approval_id else None
        ),
        "reason_code": _safe_identifier(reason_code),
        "swarm_id": safe_run_id,
        "swarm_status": swarm_status,
        "status": swarm_status,
        "child_statuses": child_statuses,
        "reconciliation": reconciliation,
    }


__all__ = [
    "APPROVAL_CONFLICT_DETAIL",
    "SWARM_APPROVAL_APPLIED_CODE",
    "SWARM_APPROVAL_PARTIAL_CODE",
    "SWARM_RESUME_CONFLICT_DETAIL",
    "approval_applied_item",
    "swarm_approval_receipt",
]
