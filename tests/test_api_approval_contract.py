"""API contracts for exact, single-use approval challenges."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from src.api import server
from src.api.server import (
    APPROVAL_CONFLICT_DETAIL,
    SWARM_APPROVAL_PARTIAL_CODE,
    SWARM_RESUME_CONFLICT_DETAIL,
    AgentApprovalRequest,
    SwarmApprovalRequest,
    agent_run_approve,
    swarm_task_approve,
)


class ApprovalApiTests(unittest.IsolatedAsyncioTestCase):
    def test_direct_approval_requires_challenge_id(self) -> None:
        with self.assertRaises(ValidationError):
            AgentApprovalRequest(step_ids=["step-1"])
        with self.assertRaises(ValidationError):
            SwarmApprovalRequest(step_ids=["step-1"])

    async def test_direct_agent_conflicts_do_not_expose_runtime_error_text(self) -> None:
        runtime = SimpleNamespace(
            approve=AsyncMock(side_effect=ValueError("secret runtime diagnostic")),
        )
        fake = SimpleNamespace(agent_runtime=runtime)
        with patch.object(server, "jarvis", fake):
            with self.assertRaises(HTTPException) as raised:
                await agent_run_approve(
                    "agent-1",
                    AgentApprovalRequest(
                        step_ids=["step-1"],
                        challenge_id="challenge-agent-0001",
                    ),
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, APPROVAL_CONFLICT_DETAIL)
        runtime.approve.assert_awaited_once_with(
            "agent-1", ["step-1"], "challenge-agent-0001",
        )

    async def test_swarm_task_resume_failure_is_returned_synchronously(self) -> None:
        task = SimpleNamespace(
            status="awaiting_confirmation", agent_run_id="agent-child",
        )
        swarm_run = SimpleNamespace(
            id="swarm-1", status="awaiting_confirmation", tasks={"task-1": task},
        )
        child = SimpleNamespace(
            status="awaiting_confirmation",
            current_step=0,
            plan=SimpleNamespace(steps=[SimpleNamespace(id="step-1")]),
        )
        agent_runtime = SimpleNamespace(
            get_run=Mock(return_value=child),
            approve=AsyncMock(return_value=SimpleNamespace(status="completed")),
        )
        swarm_runtime = SimpleNamespace(
            get_run=Mock(return_value=swarm_run),
            resume=AsyncMock(side_effect=RuntimeError("resume failed after approval")),
        )
        fake = SimpleNamespace(
            agent_runtime=agent_runtime,
            swarm_runtime=swarm_runtime,
        )

        with patch.object(server, "jarvis", fake):
            response = await swarm_task_approve(
                "swarm-1",
                "task-1",
                SwarmApprovalRequest(
                    step_ids=["step-1"],
                    challenge_id="challenge-swarm-01",
                ),
            )

        self.assertEqual(response.status_code, 409)
        receipt = json.loads(response.body)
        self.assertEqual(receipt["code"], SWARM_APPROVAL_PARTIAL_CODE)
        self.assertEqual(receipt["reason_code"], SWARM_RESUME_CONFLICT_DETAIL)
        self.assertTrue(receipt["applied"])
        self.assertTrue(receipt["partial"])
        self.assertFalse(receipt["retryable"])
        self.assertEqual(receipt["applied_count"], 1)
        self.assertEqual(receipt["requested_count"], 1)
        self.assertEqual(receipt["applied_ids"], ["agent-child:step-1"])
        self.assertEqual(receipt["swarm_status"], "awaiting_confirmation")
        self.assertEqual(receipt["reconciliation"]["action"], "refresh_before_retry")
        self.assertEqual(receipt["reconciliation"]["resume_status"], "failed")
        self.assertIn("do not retry a stale challenge", receipt["reconciliation"]["guidance"])
        self.assertNotIn("resume failed after approval", str(receipt))
        agent_runtime.approve.assert_awaited_once_with(
            "agent-child", ["step-1"], "challenge-swarm-01",
        )
        swarm_runtime.resume.assert_awaited_once_with("swarm-1")


if __name__ == "__main__":
    unittest.main()
