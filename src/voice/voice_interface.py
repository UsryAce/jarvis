"""Voice interface for Jarvis - TTS and STT."""
import asyncio
import io
import os
import tempfile
import wave
from pathlib import Path
from typing import Optional

import pyaudio

from src.config import config
from src.clients.nvidia_client import NVIDIAClient


class VoiceInterface:
    """Voice input/output using NVIDIA models."""

    def __init__(self):
        self.nvidia_client = NVIDIAClient()
        self.audio = pyaudio.PyAudio()
        self.sample_rate = config.get("voice.audio.sample_rate", 16000)
        self.channels = config.get("voice.audio.channels", 1)
        self.chunk_size = config.get("voice.audio.chunk_size", 1024)

    async def listen(self, timeout: float = 10.0) -> Optional[str]:
        """Listen for speech and return transcribed text."""
        print("🎤 Listening...")

        # Record audio
        audio_data = await self._record_audio(timeout)
        if not audio_data:
            return None

        # Transcribe
        print("🔄 Transcribing...")
        text = await self._transcribe(audio_data)
        if text:
            print(f"👤 You: {text}")
        return text

    async def _record_audio(self, timeout: float) -> Optional[bytes]:
        """Record audio from microphone."""
        frames = []
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        try:
            # Record for timeout seconds
            num_chunks = int(self.sample_rate / self.chunk_size * timeout)
            for _ in range(num_chunks):
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)

                # Simple voice activity detection
                # Check if we have enough audio data
                if len(frames) > self.sample_rate // self.chunk_size:
                    # Check volume level
                    audio_data = b''.join(frames[-10:])  # Last ~0.1s
                    if self._get_rms(audio_data) > 500:  # Threshold
                        break
        finally:
            stream.stop_stream()
            stream.close()

        if not frames:
            return None

        # Convert to WAV bytes
        return self._frames_to_wav(frames)

    def _get_rms(self, data: bytes) -> float:
        """Calculate RMS volume."""
        import struct
        count = len(data) // 2
        format_str = f"{count}h"
        shorts = struct.unpack(format_str, data)
        sum_squares = sum(s * s for s in shorts)
        return (sum_squares / count) ** 0.5

    def _frames_to_wav(self, frames: list) -> bytes:
        """Convert frames to WAV format."""
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(b''.join(frames))
            return wav_buffer.getvalue()

    async def _transcribe(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using NVIDIA ASR."""
        try:
            result = await self.nvidia_client.transcribe(audio_data)
            return result.get("text", "").strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    async def speak(self, text: str, voice: str = "female") -> bool:
        """Speak text using NVIDIA TTS."""
        print(f"🤖 Jarvis: {text}")

        try:
            audio_data = await self.nvidia_client.synthesize(text, voice=voice)
            if audio_data:
                await self._play_audio(audio_data)
                return True
        except Exception as e:
            print(f"TTS error: {e}")
        return False

    async def _play_audio(self, audio_data: bytes):
        """Play audio data."""
        # Save to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_file = f.name

        try:
            # Use system player
            import subprocess
            if os.name == 'nt':  # Windows
                subprocess.run(["powershell", "-c", f"(New-Object Media.SoundPlayer '{temp_file}').PlaySync()"])
            else:  # Linux/Mac
                subprocess.run(["aplay", temp_file] if shutil.which("aplay") else ["afplay", temp_file])
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass

    async def cleanup(self):
        """Clean up resources."""
        self.audio.terminate()
        if self.nvidia_client:
            await self.nvidia_client.__aexit__(None, None, None)


# Alternative: Use edge-tts for TTS (no API key needed)
class EdgeTTS:
    """Text-to-speech using Microsoft Edge TTS (free, no API key)."""

    def __init__(self):
        self.voice = config.get("voice.tts.voice", "en-US-JennyNeural")

    async def speak(self, text: str) -> bool:
        """Speak text using edge-tts."""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                await communicate.save(f.name)
                await self._play_file(f.name)
                os.unlink(f.name)
                return True
        except Exception as e:
            print(f"Edge TTS error: {e}")
        return False

    async def _play_file(self, filepath: str):
        """Play audio file."""
        import subprocess
        if os.name == 'nt':
            subprocess.run(["powershell", "-c", f"(New-Object Media.SoundPlayer '{filepath}').PlaySync()"])
        else:
            subprocess.run(["mpg123", filepath] if shutil.which("mpg123") else ["afplay", filepath])


# Whisper STT (local, no API key)
class WhisperSTT:
    """Speech-to-text using local Whisper model."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None

    def _load_model(self):
        """Load Whisper model."""
        if self.model is None:
            import whisper
            self.model = whisper.load_model(self.model_size)

    async def transcribe(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using Whisper."""
        try:
            self._load_model()

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_file = f.name

            # Transcribe
            result = self.model.transcribe(temp_file)
            os.unlink(temp_file)
            return result["text"].strip()
        except Exception as e:
            print(f"Whisper error: {e}")
            return None