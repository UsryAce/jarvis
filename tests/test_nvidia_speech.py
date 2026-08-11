import io
import json
import unittest
import wave
from types import SimpleNamespace

from src.voice.nvidia_speech import (
    NvidiaSpeechAdapter,
    NvidiaSpeechUnavailableError,
    NvidiaSpeechValidationError,
)


def _wav(channels=1, sample_width=2, sample_rate=16000, frames=b"\x00\x00" * 320):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
    return output.getvalue()


def _catalog(*functions):
    return json.dumps({"functions": list(functions)}).encode()


class _FakeASRService:
    def __init__(self, auth):
        self.auth = auth

    def streaming_response_generator(self, *, audio_chunks, streaming_config):
        self.chunks = list(audio_chunks)
        alternative = SimpleNamespace(transcript="hello jarvis")
        result = SimpleNamespace(is_final=True, alternatives=[alternative])
        yield SimpleNamespace(results=[result])


class _FakeTTSService:
    def __init__(self, auth):
        self.auth = auth

    def synthesize(self, **kwargs):
        return SimpleNamespace(audio=b"\x00\x00" * 200)

    def synthesize_online(self, **kwargs):
        yield SimpleNamespace(audio=b"\x01\x00" * 40)
        yield SimpleNamespace(audio=b"\x02\x00" * 60)


class _FakeRiva:
    AudioEncoding = SimpleNamespace(LINEAR_PCM="pcm", OGGOPUS="opus")
    ASRService = _FakeASRService
    SpeechSynthesisService = _FakeTTSService
    RecognitionConfig = staticmethod(lambda **kwargs: kwargs)
    StreamingRecognitionConfig = staticmethod(lambda **kwargs: kwargs)

    @staticmethod
    def Auth(**kwargs):
        return kwargs


class NvidiaSpeechAdapterTests(unittest.TestCase):
    def setUp(self):
        self.catalog_calls = []

        def fetch(url, headers, timeout):
            self.catalog_calls.append((url, headers, timeout))
            return _catalog(
                {"id": "asr-live-id", "name": "ai-parakeet-ctc-1_1b-asr", "status": "ACTIVE"},
                {"id": "tts-live-id", "name": "ai-magpie-tts-multilingual", "status": "ACTIVE"},
                {"id": "old-id", "name": "ai-old-asr", "status": "INACTIVE"},
            )

        self.adapter = NvidiaSpeechAdapter(
            "secret-test-key",
            catalog_fetcher=fetch,
            riva_loader=lambda: _FakeRiva,
        )

    def test_resolves_only_active_function_ids_and_caches_them(self):
        first = self.adapter.resolve_function("asr")
        second = self.adapter.resolve_function("asr")
        self.assertEqual(first.function_id, "asr-live-id")
        self.assertEqual(first, second)
        self.assertEqual(len(self.catalog_calls), 1)
        authorization = self.catalog_calls[0][1]["Authorization"]
        self.assertEqual(authorization, "Bearer secret-test-key")

    def test_status_never_exposes_api_key(self):
        status = self.adapter.status(probe_catalog=True)
        serialized = json.dumps(status)
        self.assertTrue(status["available"])
        self.assertNotIn("secret-test-key", serialized)
        self.assertEqual(status["catalog"]["active"]["asr"], "ai-parakeet-ctc-1_1b-asr")

    def test_missing_dependency_is_a_graceful_unavailable_state(self):
        def missing():
            raise ModuleNotFoundError("No module named 'riva'")

        adapter = NvidiaSpeechAdapter("configured", riva_loader=missing)
        status = adapter.status()
        self.assertFalse(status["available"])
        self.assertFalse(status["dependency_installed"])
        with self.assertRaises(NvidiaSpeechUnavailableError):
            adapter.transcribe(_wav())

    def test_missing_key_is_a_graceful_unavailable_state(self):
        adapter = NvidiaSpeechAdapter(api_key="", riva_loader=lambda: _FakeRiva)
        adapter._api_key = None
        status = adapter.status()
        self.assertFalse(status["available"])
        self.assertIn("NVIDIA_API_KEY", status["reason"])
        with self.assertRaises(NvidiaSpeechUnavailableError):
            adapter.resolve_function("asr")

    def test_validates_and_unpacks_mono_pcm_wav(self):
        payload = self.adapter.validate_audio(_wav(), "recording.wav")
        self.assertEqual(payload.encoding_name, "LINEAR_PCM")
        self.assertEqual(payload.sample_rate_hz, 16000)
        self.assertEqual(len(payload.data), 640)

    def test_rejects_stereo_and_non_pcm16_wav(self):
        with self.assertRaisesRegex(NvidiaSpeechValidationError, "mono"):
            self.adapter.validate_audio(_wav(channels=2), "stereo.wav")
        with self.assertRaisesRegex(NvidiaSpeechValidationError, "16-bit PCM"):
            self.adapter.validate_audio(_wav(sample_width=1), "eight-bit.wav")

    def test_validates_mono_ogg_opus_header(self):
        mono_opus = b"OggS" + b"\x00" * 20 + b"OpusHead" + b"\x01\x01" + b"payload"
        payload = self.adapter.validate_audio(mono_opus, "voice.opus")
        self.assertEqual(payload.encoding_name, "OGGOPUS")
        self.assertEqual(payload.sample_rate_hz, 0)

        stereo_opus = b"OggS" + b"\x00" * 20 + b"OpusHead" + b"\x01\x02" + b"payload"
        with self.assertRaisesRegex(NvidiaSpeechValidationError, "mono Opus"):
            self.adapter.validate_audio(stereo_opus, "voice.ogg")

    def test_transcribes_and_synthesizes_wav(self):
        self.assertEqual(self.adapter.transcribe(_wav()), "hello jarvis")
        synthesized = self.adapter.synthesize("Ready.", voice_name="TestVoice")
        with wave.open(io.BytesIO(synthesized), "rb") as wav_file:
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getsampwidth(), 2)
            self.assertEqual(wav_file.getframerate(), 44100)
            self.assertGreater(wav_file.getnframes(), 0)

    def test_streams_pcm_chunks_without_waiting_for_a_wav(self):
        chunks = list(self.adapter.synthesize_stream("Ready.", voice_name="TestVoice"))
        self.assertEqual([len(chunk) for chunk in chunks], [80, 120])


if __name__ == "__main__":
    unittest.main()
