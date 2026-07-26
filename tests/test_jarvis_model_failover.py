from __future__ import annotations

from contextvars import ContextVar

import pytest

from src.clients.provider_factory import ProviderSafeError
from src.core.jarvis import Jarvis
from src.core.model_router import PRIMARY_MODEL


class _FailoverClient:
    def __init__(self):
        self.models: list[str] = []

    async def chat_completion(self, _messages, *, model, max_tokens):
        del max_tokens
        self.models.append(model)
        if model == PRIMARY_MODEL:
            raise ProviderSafeError(code="indeterminate", correlation_id="test")
        return {"choices": [{"message": {"content": "fallback ok"}}]}


@pytest.mark.asyncio
async def test_auto_response_fails_over_from_unavailable_primary():
    jarvis = Jarvis.__new__(Jarvis)
    client = _FailoverClient()
    jarvis._require_provider_client = lambda: _client(client)
    jarvis.model_router = type("Router", (), {"PRIMARY_MODEL": PRIMARY_MODEL})()
    jarvis._model_catalog = {PRIMARY_MODEL, "deepseek-ai/deepseek-v4-flash"}
    jarvis._model_disabled_until = {}
    jarvis._response_model = ContextVar("test_response_model", default=None)
    jarvis.conversation_history = []
    jarvis.memory = None

    result = await jarvis._get_response(
        [{"role": "user", "content": "hello"}],
        PRIMARY_MODEL,
        "hello",
        16,
        fallback_models=(PRIMARY_MODEL, "deepseek-ai/deepseek-v4-flash"),
    )

    assert result == "fallback ok"
    assert client.models == [PRIMARY_MODEL, "deepseek-ai/deepseek-v4-flash"]
    assert jarvis._model_disabled_until[PRIMARY_MODEL] > 0
    assert jarvis.response_model == "deepseek-ai/deepseek-v4-flash"


async def _client(client):
    return client
