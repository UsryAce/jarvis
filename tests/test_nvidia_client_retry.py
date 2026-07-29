import unittest
from unittest.mock import AsyncMock, patch

from src.clients.nvidia_client import NVIDIAClient


class _FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self.payload = payload or {}
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def json(self):
        return self.payload

    async def read(self):
        return b""


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def post(self, *_args, **_kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response


class NvidiaClientRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_retries_transient_service_error(self):
        expected = {"choices": [{"message": {"content": "ready"}}]}
        session = _FakeSession([_FakeResponse(503), _FakeResponse(200, expected)])
        client = NVIDIAClient(api_key="test-key")
        client._session = session
        with patch("src.clients.nvidia_client.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await client.chat_completion([{"role": "user", "content": "hello"}])
        self.assertEqual(result, expected)
        self.assertEqual(session.calls, 2)
        sleep.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
