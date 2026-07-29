import unittest
from unittest.mock import AsyncMock

from src.memory.vector_memory import VectorMemory


class VectorMemoryCircuitTests(unittest.IsolatedAsyncioTestCase):
    async def test_embedding_failure_opens_circuit_and_uses_local_fallback(self):
        memory = VectorMemory()
        error = RuntimeError("bad embedding request")
        error.status = 400
        memory.nvidia_client = type("Client", (), {"embeddings": AsyncMock(side_effect=error)})()

        first = await memory._get_embeddings(["hello"])
        second = await memory._get_embeddings(["hello"])

        self.assertEqual(first, second)
        self.assertEqual(len(first[0]), 1024)
        self.assertEqual(memory.nvidia_client.embeddings.await_count, 1)
        self.assertGreater(memory._embedding_disabled_until, 0)


if __name__ == "__main__":
    unittest.main()
