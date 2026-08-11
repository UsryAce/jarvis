"""Optional cloud adapter for NVIDIA Nemotron Speech (Riva) NIMs.

The adapter intentionally imports ``nvidia-riva-client`` lazily.  JARVIS can
therefore start and report a useful unavailable state when the optional speech
dependency is not installed.
"""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import threading
import time
import wave
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, Optional
from urllib.request import Request, urlopen

from src.clients.nvidia_client import _ProtectedEphemeralCredential, _legacy_provider_context
from src.clients.provider_factory import ProviderFactory, ProviderSafeError

NVCF_FUNCTIONS_URL = (
    "https://api.nvcf.nvidia.com/v2/nvcf/functions"
    "?visibility=public,authorized"
)
NVCF_GRPC_ENDPOINT = "grpc.nvcf.nvidia.com:443"

DEFAULT_ASR_FUNCTION = "ai-parakeet-ctc-1_1b-asr"
DEFAULT_TTS_FUNCTION = "ai-magpie-tts-multilingual"


class NvidiaSpeechError(RuntimeError):
    """Base error for Nemotron Speech operations."""


class NvidiaSpeechUnavailableError(NvidiaSpeechError):
    """Raised when credentials, dependencies, or an active NVCF model are absent."""


class NvidiaSpeechValidationError(ValueError):
    """Raised when audio cannot be safely sent to Riva ASR."""


@dataclass(frozen=True)
class FunctionRef:
    """An ACTIVE cloud function selected from the live NVCF catalog."""

    function_id: str
    name: str


@dataclass(frozen=True)
class AudioPayload:
    """Validated audio ready for the Riva recognition API."""

    data: bytes
    encoding_name: str
    sample_rate_hz: int


CatalogFetcher = Callable[[str, Mapping[str, str], float], bytes]
RivaLoader = Callable[[], Any]


class NvidiaSpeechAdapter:
    """Cloud-first ASR/TTS adapter backed by NVIDIA NVCF-hosted Riva NIMs.

    Function IDs are discovered from the authenticated NVCF functions catalog
    and are never embedded in source.  A short cache avoids a catalog request on
    every utterance while still allowing rotating function versions to refresh.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        provider_factory: ProviderFactory | None = None,
        credential_handle: str | None = None,
        expected_generation: int | None = None,
        provider: str = "nvidia",
        endpoint: str = NVCF_GRPC_ENDPOINT,
        timeout_seconds: float = 15.0,
        catalog_ttl_seconds: float = 300.0,
        catalog_fetcher: Optional[CatalogFetcher] = None,
        riva_loader: Optional[RivaLoader] = None,
    ) -> None:
        self.provider = provider.casefold()
        self._api_key = None  # Compatibility sentinel; raw keys are never retained.
        self._legacy_credential: _ProtectedEphemeralCredential | None = None
        if provider_factory is None and api_key:
            (
                provider_factory,
                credential_handle,
                expected_generation,
                self._legacy_credential,
            ) = _legacy_provider_context(api_key)
        self.provider_factory = provider_factory
        self.credential_handle = credential_handle
        self.expected_generation = (
            int(provider_factory.credential_service.provider_generation(self.provider))
            if provider_factory is not None
            and credential_handle is not None
            and expected_generation is None
            else expected_generation
        )
        self.endpoint = endpoint
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.catalog_ttl_seconds = max(0.0, float(catalog_ttl_seconds))
        self._catalog_fetcher = catalog_fetcher or self._fetch_catalog
        self._riva_loader = riva_loader or self._import_riva
        self._riva: Any = None
        self._function_cache: dict[tuple[int, str], tuple[float, FunctionRef]] = {}
        self._cache_lock = threading.Lock()
        self._invalidated = False

    @staticmethod
    def _import_riva() -> Any:
        return importlib.import_module("riva.client")

    @staticmethod
    def _fetch_catalog(url: str, headers: Mapping[str, str], timeout: float) -> bytes:
        # The URL is a constant rather than caller-controlled input.  Credentials
        # are transmitted in a header and are never included in an exception.
        request = Request(url, headers=dict(headers))
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read(4 * 1024 * 1024 + 1)

    def capabilities(self) -> dict[str, Any]:
        """Return stable adapter capabilities without making a network request."""
        return {
            "provider": "nvidia_nemotron_speech",
            "deployment": "cloud",
            "transport": "grpc_tls",
            "endpoint": self.endpoint,
            "asr": {
                "supported": True,
                "formats": ["wav_pcm_s16le", "ogg_opus"],
                "channels": 1,
                "default_function": DEFAULT_ASR_FUNCTION,
            },
            "tts": {
                "supported": True,
                "output_format": "wav_pcm_s16le",
                "default_function": DEFAULT_TTS_FUNCTION,
                "voices": "discover_from_active_model",
            },
            "sends_audio_to_cloud": True,
        }

    def status(self, *, probe_catalog: bool = False) -> dict[str, Any]:
        """Return a secret-free availability report, optionally probing NVCF."""
        dependency_installed = True
        dependency_error: Optional[str] = None
        try:
            self._load_riva()
        except NvidiaSpeechUnavailableError as exc:
            dependency_installed = False
            dependency_error = str(exc)

        configured = (
            self.provider_factory is not None
            and self.credential_handle is not None
            and self.expected_generation is not None
            and not self._invalidated
        )
        available = configured and dependency_installed
        reason: Optional[str] = None
        if not configured:
            reason = (
                "NVIDIA_API_KEY is not imported at runtime; configure an opaque "
                "NVIDIA credential handle"
            )
        elif dependency_error:
            reason = dependency_error

        catalog: dict[str, Any] = {"probed": False}
        if available and probe_catalog:
            catalog = {"probed": True, "reachable": False}
            try:
                asr = self.resolve_function("asr")
                tts = self.resolve_function("tts")
                catalog.update(
                    reachable=True,
                    active={"asr": asr.name, "tts": tts.name},
                )
            except NvidiaSpeechError as exc:
                available = False
                reason = str(exc)
                catalog["error"] = str(exc)

        return {
            "provider": "nvidia_nemotron_speech",
            "configured": configured,
            "dependency_installed": dependency_installed,
            "available": available,
            "reason": reason,
            "catalog": catalog,
        }

    def _load_riva(self) -> Any:
        if self._riva is not None:
            return self._riva
        try:
            self._riva = self._riva_loader()
        except (ImportError, ModuleNotFoundError) as exc:
            raise NvidiaSpeechUnavailableError(
                "NVIDIA speech is unavailable because nvidia-riva-client is not installed"
            ) from exc
        return self._riva

    def invalidate(self) -> None:
        """Fence in-flight cache state after a provider generation change."""
        with self._cache_lock:
            self._function_cache.clear()
            self._riva = None
            self._invalidated = True

    @contextmanager
    def _request_lease(self) -> Iterator[Any]:
        if (
            self.provider_factory is None
            or self.credential_handle is None
            or self.expected_generation is None
            or self._invalidated
        ):
            raise NvidiaSpeechUnavailableError(
                "NVIDIA speech is unavailable because no usable credential handle exists"
            )
        try:
            with self.provider_factory.request_lease(
                provider=self.provider,
                credential_handle=self.credential_handle,
                expected_generation=self.expected_generation,
                required_scope="provider.request",
                granted_scopes=("provider.request",),
                correlation_id=f"speech-{time.monotonic_ns()}",
            ) as lease:
                yield lease
        except ProviderSafeError as exc:
            raise NvidiaSpeechUnavailableError(exc.code) from None

    def _read_active_functions(self) -> list[FunctionRef]:
        try:
            with self._request_lease() as lease:
                headers = lease.headers_for_send(
                    additional={
                        "Accept": "application/json",
                        "User-Agent": "Jarvis-NemotronSpeech/1.0",
                    }
                )
                payload = self._catalog_fetcher(
                    NVCF_FUNCTIONS_URL, dict(headers), self.timeout_seconds
                )
            if len(payload) > 4 * 1024 * 1024:
                raise ValueError("response exceeds 4 MiB")
            document = json.loads(payload.decode("utf-8"))
        except Exception as exc:
            raise NvidiaSpeechUnavailableError(
                "Unable to discover active NVIDIA speech functions"
            ) from exc

        raw_functions = document.get("functions") if isinstance(document, dict) else None
        if not isinstance(raw_functions, list):
            raise NvidiaSpeechUnavailableError(
                "NVIDIA function catalog returned an invalid response"
            )

        active: list[FunctionRef] = []
        for item in raw_functions:
            if not isinstance(item, dict) or str(item.get("status", "")).upper() != "ACTIVE":
                continue
            function_id = str(item.get("id", "")).strip()
            name = str(item.get("name", "")).strip()
            if function_id and name:
                active.append(FunctionRef(function_id=function_id, name=name))
        return active

    def resolve_function(
        self,
        modality: str,
        function_name: Optional[str] = None,
        *,
        force_refresh: bool = False,
    ) -> FunctionRef:
        """Resolve an ACTIVE NVCF function ID for ``asr`` or ``tts``."""
        modality = modality.casefold().strip()
        if modality not in {"asr", "tts"}:
            raise ValueError("modality must be 'asr' or 'tts'")
        requested = function_name or (
            DEFAULT_ASR_FUNCTION if modality == "asr" else DEFAULT_TTS_FUNCTION
        )
        if self.expected_generation is None:
            raise NvidiaSpeechUnavailableError(
                "NVIDIA speech is unavailable because no usable credential handle exists"
            )
        cache_key = (
            self.expected_generation,
            f"{modality}:{requested.casefold()}",
        )
        now = time.monotonic()
        with self._cache_lock:
            cached = self._function_cache.get(cache_key)
            if cached and not force_refresh and cached[0] > now:
                return cached[1]

        active = self._read_active_functions()
        normalized = _normalize_function_name(requested)
        exact = [item for item in active if _normalize_function_name(item.name) == normalized]
        if exact:
            selected = exact[0]
        else:
            terms = ("parakeet", "canary", "whisper", "nemotron-asr") if modality == "asr" else ("magpie", "tts")
            matches = [item for item in active if any(term in item.name.casefold() for term in terms)]
            if not matches:
                raise NvidiaSpeechUnavailableError(
                    f"No ACTIVE NVIDIA {modality.upper()} function is available"
                )
            selected = matches[0]

        with self._cache_lock:
            self._function_cache[cache_key] = (
                now + self.catalog_ttl_seconds,
                selected,
            )
        return selected

    def validate_audio(self, audio_data: bytes, filename: str = "audio.wav") -> AudioPayload:
        """Validate and unpack a mono WAV or validate a mono Ogg Opus stream."""
        if not isinstance(audio_data, (bytes, bytearray)) or not audio_data:
            raise NvidiaSpeechValidationError("Audio must be non-empty bytes")
        raw = bytes(audio_data)
        lower_name = filename.casefold().strip()
        is_wav = lower_name.endswith(".wav") or raw.startswith(b"RIFF")
        is_opus = lower_name.endswith((".opus", ".ogg")) or raw.startswith(b"OggS")

        if is_wav:
            try:
                with wave.open(io.BytesIO(raw), "rb") as wav_file:
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    sample_rate = wav_file.getframerate()
                    compression = wav_file.getcomptype()
                    frames = wav_file.readframes(wav_file.getnframes())
            except (wave.Error, EOFError) as exc:
                raise NvidiaSpeechValidationError("Invalid WAV audio") from exc
            if channels != 1:
                raise NvidiaSpeechValidationError(
                    "Riva ASR accepts mono audio only; downmix with ffmpeg -ac 1"
                )
            if sample_width != 2 or compression != "NONE":
                raise NvidiaSpeechValidationError(
                    "WAV audio must be uncompressed 16-bit PCM (pcm_s16le)"
                )
            if sample_rate <= 0 or not frames:
                raise NvidiaSpeechValidationError("WAV audio contains no usable samples")
            return AudioPayload(frames, "LINEAR_PCM", sample_rate)

        if is_opus:
            if not raw.startswith(b"OggS"):
                raise NvidiaSpeechValidationError("Opus audio must use an Ogg container")
            opus_head = raw.find(b"OpusHead", 0, min(len(raw), 65536))
            if opus_head < 0 or opus_head + 10 > len(raw):
                raise NvidiaSpeechValidationError("Invalid Ogg Opus audio: OpusHead is missing")
            channels = raw[opus_head + 9]
            if channels != 1:
                raise NvidiaSpeechValidationError(
                    "Riva ASR accepts mono Opus only; downmix with ffmpeg -ac 1"
                )
            return AudioPayload(raw, "OGGOPUS", 0)

        raise NvidiaSpeechValidationError(
            "Unsupported audio format; use mono 16-bit PCM WAV or mono Ogg Opus"
        )

    def _auth(self, function: FunctionRef, lease: Any) -> Any:
        riva = self._load_riva()
        headers = lease.headers_for_send()
        metadata = [
            ["function-id", function.function_id],
            ["authorization", headers["Authorization"]],
        ]
        return riva.Auth(uri=self.endpoint, use_ssl=True, metadata_args=metadata)

    def transcribe(
        self,
        audio_data: bytes,
        *,
        filename: str = "audio.wav",
        language_code: str = "en-US",
        function_name: Optional[str] = None,
        automatic_punctuation: bool = True,
    ) -> str:
        """Transcribe validated audio with an ACTIVE NVIDIA cloud ASR NIM."""
        payload = self.validate_audio(audio_data, filename)
        function = self.resolve_function("asr", function_name)
        riva = self._load_riva()
        encoding = getattr(riva.AudioEncoding, payload.encoding_name)
        config = riva.RecognitionConfig(
            language_code=language_code,
            sample_rate_hertz=payload.sample_rate_hz,
            audio_channel_count=1,
            encoding=encoding,
            enable_automatic_punctuation=automatic_punctuation,
            max_alternatives=1,
        )
        streaming_config = riva.StreamingRecognitionConfig(
            config=config, interim_results=False
        )
        chunk_size = (
            max(3200, payload.sample_rate_hz * 2)
            if payload.encoding_name == "LINEAR_PCM"
            else 8192
        )
        chunks = (
            payload.data[index : index + chunk_size]
            for index in range(0, len(payload.data), chunk_size)
        )
        transcripts: list[str] = []
        try:
            with self._request_lease() as lease:
                service = riva.ASRService(self._auth(function, lease))
                responses = service.streaming_response_generator(
                    audio_chunks=chunks, streaming_config=streaming_config
                )
                for response in responses:
                    lease.require_send_allowed()
                    for result in getattr(response, "results", ()):
                        alternatives = getattr(result, "alternatives", ())
                        if getattr(result, "is_final", False) and alternatives:
                            text = str(getattr(alternatives[0], "transcript", "")).strip()
                            if text:
                                transcripts.append(text)
        except Exception as exc:
            raise NvidiaSpeechError("NVIDIA ASR request failed") from exc
        return " ".join(transcripts)

    async def transcribe_async(self, audio_data: bytes, **kwargs: Any) -> str:
        """Non-blocking event-loop wrapper for :meth:`transcribe`."""
        return await asyncio.to_thread(self.transcribe, audio_data, **kwargs)

    def synthesize(
        self,
        text: str,
        *,
        voice_name: str,
        language_code: str = "en-US",
        sample_rate_hz: int = 44100,
        function_name: Optional[str] = None,
    ) -> bytes:
        """Synthesize speech and return a mono 16-bit PCM WAV byte stream."""
        if not text or not text.strip():
            raise NvidiaSpeechValidationError("Speech text must not be empty")
        if not voice_name or not voice_name.strip():
            raise NvidiaSpeechValidationError(
                "voice_name is required and must come from the active model's voice list"
            )
        if sample_rate_hz <= 0:
            raise NvidiaSpeechValidationError("sample_rate_hz must be positive")
        function = self.resolve_function("tts", function_name)
        riva = self._load_riva()
        try:
            with self._request_lease() as lease:
                service = riva.SpeechSynthesisService(self._auth(function, lease))
                response = service.synthesize(
                    text=text.strip(),
                    voice_name=voice_name.strip(),
                    language_code=language_code,
                    encoding=riva.AudioEncoding.LINEAR_PCM,
                    sample_rate_hz=sample_rate_hz,
                )
                pcm = bytes(response.audio)
        except Exception as exc:
            raise NvidiaSpeechError("NVIDIA TTS request failed") from exc
        if not pcm:
            raise NvidiaSpeechError("NVIDIA TTS returned empty audio")
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate_hz)
            wav_file.writeframes(pcm)
        return output.getvalue()

    async def synthesize_async(self, text: str, **kwargs: Any) -> bytes:
        """Non-blocking event-loop wrapper for :meth:`synthesize`."""
        return await asyncio.to_thread(self.synthesize, text, **kwargs)

    def synthesize_stream(
        self,
        text: str,
        *,
        voice_name: str,
        language_code: str = "en-US",
        sample_rate_hz: int = 22050,
        function_name: Optional[str] = None,
    ) -> Iterator[bytes]:
        """Yield raw mono PCM16 chunks as Magpie produces them."""
        if not text or not text.strip():
            raise NvidiaSpeechValidationError("Speech text must not be empty")
        if not voice_name or not voice_name.strip():
            raise NvidiaSpeechValidationError("voice_name is required")
        function = self.resolve_function("tts", function_name)
        riva = self._load_riva()
        try:
            with self._request_lease() as lease:
                service = riva.SpeechSynthesisService(self._auth(function, lease))
                for response in service.synthesize_online(
                    text=text.strip(),
                    voice_name=voice_name.strip(),
                    language_code=language_code,
                    encoding=riva.AudioEncoding.LINEAR_PCM,
                    sample_rate_hz=sample_rate_hz,
                ):
                    lease.require_send_allowed()
                    chunk = bytes(response.audio)
                    if chunk:
                        yield chunk
        except Exception as exc:
            raise NvidiaSpeechError("NVIDIA streaming TTS request failed") from exc


def _normalize_function_name(name: str) -> str:
    normalized = name.casefold().strip()
    if normalized.startswith("ai-"):
        normalized = normalized[3:]
    return normalized.replace("_", "-")


__all__ = [
    "AudioPayload",
    "FunctionRef",
    "NVCF_FUNCTIONS_URL",
    "NVCF_GRPC_ENDPOINT",
    "NvidiaSpeechAdapter",
    "NvidiaSpeechError",
    "NvidiaSpeechUnavailableError",
    "NvidiaSpeechValidationError",
]
