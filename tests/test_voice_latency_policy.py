"""Tests for the low-latency policy used by spoken JARVIS turns."""

import unittest

from src.core.jarvis import Jarvis


class VoiceLatencyPolicyTests(unittest.TestCase):
    def test_normal_voice_turn_skips_remote_long_term_memory_lookup(self):
        self.assertFalse(Jarvis._voice_needs_long_term_memory("Is the system ready?"))
        self.assertFalse(Jarvis._voice_needs_long_term_memory("Tell me a short joke"))

    def test_explicit_voice_recall_keeps_long_term_memory_lookup(self):
        self.assertTrue(Jarvis._voice_needs_long_term_memory("Do you remember my preferred model?"))
        self.assertTrue(Jarvis._voice_needs_long_term_memory("What did I tell you last time?"))


class DirectVoiceStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_skill_result_uses_normal_stream_shape(self):
        chunks = [chunk async for chunk in Jarvis._stream_text("Current time: 09:30 AM")]
        self.assertEqual(chunks, ["Current time: 09:30 AM"])
