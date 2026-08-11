from __future__ import annotations

from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.agent import AgentRuntime
from src.core.jarvis import Jarvis
from src.core.model_router import RouteDecision


@pytest.mark.asyncio
async def test_file_action_chat_queues_guarded_agent_without_running_legacy_skills():
    jarvis = Jarvis.__new__(Jarvis)
    jarvis._initialized = True
    jarvis._response_model = ContextVar("test_chat_dispatch_model", default=None)
    jarvis._require_runtime_effect = lambda _boundary: None
    jarvis.route_model = AsyncMock(return_value=RouteDecision(
        model="z-ai/glm-5.2",
        task_category="coding",
        reason="test",
        auto_mode=True,
    ))
    submit = AsyncMock(return_value=SimpleNamespace(id="agent-test123", status="queued"))
    jarvis.agent_runtime = SimpleNamespace(
        should_delegate_chat_action=AgentRuntime.should_delegate_chat_action,
        submit=submit,
    )
    legacy_execute = AsyncMock(return_value="legacy mutation")
    jarvis.skills = SimpleNamespace(execute_if_applicable=legacy_execute)
    jarvis.conversation_history = []
    jarvis.memory = None

    message = "Delete the temporary file demo.txt"
    result = await Jarvis.chat(jarvis, message, use_memory=False)

    assert "agent-test123" in result
    assert "queued" in result
    submit.assert_awaited_once_with(
        message,
        model="z-ai/glm-5.2",
        autonomy="guarded",
    )
    legacy_execute.assert_not_awaited()
    assert jarvis.conversation_history[-1]["agent_run_id"] == "agent-test123"
