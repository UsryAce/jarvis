"""NVIDIA API clients using opaque, request-scoped credential leases."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, AsyncGenerator, Dict, Iterator, List, Optional, Union

import aiohttp

from src.clients.provider_factory import ProviderFactory, ProviderSafeError
from src.config import config
from src.models.nvidia_models import (
    ModelType,
    NVIDIAModel,
    get_model_by_id,
    get_recommended_embedding_model,
    get_recommended_reranker,
)
from src.security.secrets import CurrentUserDpapiProtector


_TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})


class _ProtectedEphemeralCredential:
    """DPAPI-sealed compatibility input; never retains constructor plaintext."""

    def __init__(self, api_key: str, provider: str = "nvidia") -> None:
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("opaque NVIDIA credential handle required")
        self.provider = provider
        self.credential_handle = str(uuid.uuid4())
        self.generation = 1
        self._protector = CurrentUserDpapiProtector()
        self._entropy = bytearray(os.urandom(32))
        plaintext = bytearray(api_key.encode("utf-8"))
        try:
            self._ciphertext = self._protector.protect(
                plaintext,
                purpose="provider-credential",
                entropy=self._entropy,
            )
        finally:
            _zero(plaintext)

    def provider_generation(self, provider: str) -> int:
        if provider.casefold() != self.provider:
            raise ValueError("provider_invalid")
        return self.generation

    @contextmanager
    def lease_secret(
        self, credential_id: str, *, expected_generation: int
    ) -> Iterator[bytearray]:
        if (
            credential_id != self.credential_handle
            or expected_generation != self.generation
        ):
            error = RuntimeError("credential_lease_rejected")
            error.code = "credential_lease_rejected"
            raise error
        plaintext = self._protector.unprotect(
            self._ciphertext,
            purpose="provider-credential",
            entropy=self._entropy,
        )
        try:
            yield plaintext
        finally:
            _zero(plaintext)

    def close(self) -> None:
        _zero(self._ciphertext)
        _zero(self._entropy)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def _legacy_provider_context(
    api_key: str,
) -> tuple[ProviderFactory, str, int, _ProtectedEphemeralCredential]:
    """Seal an explicitly supplied legacy key for compatibility-only callers."""
    credential = _ProtectedEphemeralCredential(api_key)
    factory = ProviderFactory(credential_service=credential)
    return factory, credential.credential_handle, credential.generation, credential


class NVIDIAClient:
    """Async NVIDIA client whose persistent state is secret-free."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
        *,
        provider_factory: ProviderFactory | None = None,
        credential_handle: str | None = None,
        expected_generation: int | None = None,
        provider: str = "nvidia",
        granted_scopes: tuple[str, ...] = ("provider.request",),
    ) -> None:
        self.provider = provider.casefold()
        self.base_url = base_url or config.get(
            "nvidia.api_base", "https://integrate.api.nvidia.com/v1"
        )
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._owns_session = False
        self._legacy_credential: _ProtectedEphemeralCredential | None = None
        if provider_factory is None and api_key:
            (
                provider_factory,
                credential_handle,
                expected_generation,
                self._legacy_credential,
            ) = _legacy_provider_context(api_key)
        if provider_factory is None or credential_handle is None:
            raise ValueError("opaque NVIDIA credential handle and ProviderFactory required")
        self.provider_factory = provider_factory
        self.credential_handle = credential_handle
        self.expected_generation = (
            int(provider_factory.credential_service.provider_generation(self.provider))
            if expected_generation is None
            else int(expected_generation)
        )
        self.granted_scopes = tuple(granted_scopes)
        self._invalidated = False

    async def __aenter__(self) -> "NVIDIAClient":
        self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None and self._owns_session:
            await session.close()
        self._owns_session = False
        if self._legacy_credential is not None:
            self._legacy_credential.close()

    def invalidate(self) -> None:
        """Fence this client after credential lifecycle generation changes."""
        self._invalidated = True

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            self._owns_session = True
        return self._session

    @contextmanager
    def _request_lease(self) -> Iterator[Any]:
        if self._invalidated:
            raise ProviderSafeError(
                code="stale_generation", correlation_id=_correlation_id()
            )
        correlation_id = _correlation_id()
        with self.provider_factory.request_lease(
            provider=self.provider,
            credential_handle=self.credential_handle,
            expected_generation=self.expected_generation,
            required_scope="provider.request",
            granted_scopes=self.granted_scopes,
            correlation_id=correlation_id,
        ) as lease:
            yield lease

    async def _json_request(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        data: Any = None,
        retries: int = 1,
    ) -> Dict:
        session = self._get_session()
        for attempt in range(retries):
            with self._request_lease() as lease:
                headers = lease.headers_for_send(
                    additional={"Content-Type": "application/json"}
                    if data is None
                    else None
                )
                request = getattr(session, method.casefold())
                kwargs: dict[str, Any] = {"headers": headers}
                if payload is not None:
                    kwargs["json"] = payload
                if data is not None:
                    kwargs["data"] = data
                async with request(f"{self.base_url}{path}", **kwargs) as response:
                    status = int(response.status)
                    if status in _TRANSIENT_STATUSES and attempt + 1 < retries:
                        delay = _retry_delay(response, attempt)
                        await response.read()
                    else:
                        _raise_for_status(status, lease.correlation_id)
                        return await response.json()
            await asyncio.sleep(delay)
        raise ProviderSafeError(code="indeterminate", correlation_id=_correlation_id())

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        stream: bool = False,
        **kwargs: Any,
    ) -> Dict:
        payload = {
            "model": model or "meta/llama-3.1-70b-instruct",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": stream,
            **kwargs,
        }
        return await self._json_request(
            "post", "/chat/completions", payload=payload, retries=3
        )

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict, None]:
        payload = {
            "model": model or "meta/llama-3.1-70b-instruct",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }
        session = self._get_session()
        for attempt in range(3):
            with self._request_lease() as lease:
                headers = lease.headers_for_send(
                    additional={"Content-Type": "application/json"}
                )
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    status = int(response.status)
                    if status in _TRANSIENT_STATUSES and attempt < 2:
                        delay = _retry_delay(response, attempt)
                        await response.read()
                    else:
                        _raise_for_status(status, lease.correlation_id)
                        async for line in response.content:
                            lease.require_send_allowed()
                            line = line.decode("utf-8").strip()
                            if not line.startswith("data: "):
                                continue
                            data = line[6:]
                            if data == "[DONE]":
                                return
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                continue
                        return
            await asyncio.sleep(delay)

    async def embeddings(
        self,
        texts: Union[str, List[str]],
        model: Optional[str] = None,
        input_type: str = "query",
    ) -> Dict:
        inputs = [texts] if isinstance(texts, str) else texts
        return await self._json_request(
            "post",
            "/embeddings",
            payload={
                "model": model or get_recommended_embedding_model().id,
                "input": inputs,
                "input_type": input_type,
            },
        )

    async def rerank(
        self,
        query: str,
        passages: List[str],
        model: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict:
        return await self._json_request(
            "post",
            "/rerank",
            payload={
                "model": model or get_recommended_reranker().id,
                "query": query,
                "passages": passages,
                "top_k": top_k,
            },
        )

    async def vision(
        self,
        image_url: str,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Dict:
        return await self.chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            model=model or "microsoft/phi-3.5-vision-instruct",
            max_tokens=max_tokens,
        )

    async def synthesize(
        self,
        text: str,
        model: Optional[str] = None,
        voice: str = "female",
        sample_rate: int = 22050,
    ) -> bytes:
        session = self._get_session()
        with self._request_lease() as lease:
            headers = lease.headers_for_send(
                additional={"Content-Type": "application/json"}
            )
            async with session.post(
                f"{self.base_url}/audio/speech",
                json={
                    "model": model or "nvidia/tts_en_us_fastpitch_hifigan",
                    "input": text,
                    "voice": voice,
                    "sample_rate": sample_rate,
                },
                headers=headers,
            ) as response:
                _raise_for_status(int(response.status), lease.correlation_id)
                return await response.read()

    async def transcribe(
        self,
        audio_data: bytes,
        model: Optional[str] = None,
        language: str = "en",
        response_format: str = "json",
    ) -> Dict:
        form = aiohttp.FormData()
        form.add_field("model", model or "nvidia/stt_en_conformer_transducer_large")
        form.add_field("language", language)
        form.add_field("response_format", response_format)
        form.add_field(
            "file", audio_data, filename="audio.wav", content_type="audio/wav"
        )
        return await self._json_request("post", "/audio/transcriptions", data=form)

    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        n: int = 1,
        size: str = "1024x1024",
        response_format: str = "url",
    ) -> Dict:
        return await self._json_request(
            "post",
            "/images/generations",
            payload={
                "model": model or "stabilityai/stable-diffusion-xl-base-1.0",
                "prompt": prompt,
                "n": n,
                "size": size,
                "response_format": response_format,
            },
        )

    async def list_models(self) -> Dict:
        return await self._json_request("get", "/models")

    def get_available_models(self) -> Dict[ModelType, List[NVIDIAModel]]:
        from src.models.nvidia_models import ALL_MODELS

        return ALL_MODELS

    def get_recommended_model(self, task: str) -> NVIDIAModel:
        task_models = {
            "chat": "nvidia/llama-3.1-nemotron-70b-instruct",
            "coding": "deepseek-ai/deepseek-coder-v2-lite-instruct",
            "reasoning": "meta/llama-3.1-405b-instruct",
            "efficient": "z.ai/glm-4.5-air",
            "edge": "microsoft/phi-3.5-mini-instruct",
            "embedding": get_recommended_embedding_model().id,
            "reranking": get_recommended_reranker().id,
            "vision": "microsoft/phi-3.5-vision-instruct",
            "tts": "nvidia/tts_en_us_fastpitch_hifigan",
            "stt": "nvidia/stt_en_conformer_transducer_large",
            "image_gen": "stabilityai/stable-diffusion-xl-base-1.0",
        }
        return get_model_by_id(task_models.get(task, task_models["chat"]))


class SyncNVIDIAClient:
    """Synchronous wrapper sharing the same opaque provider context."""

    def __init__(
        self,
        *,
        provider_factory: ProviderFactory | None = None,
        credential_handle: str | None = None,
        expected_generation: int | None = None,
        provider: str = "nvidia",
    ) -> None:
        self.provider_factory = provider_factory
        self.credential_handle = credential_handle
        self.expected_generation = expected_generation
        self.provider = provider

    def _client(self) -> NVIDIAClient:
        return NVIDIAClient(
            provider_factory=self.provider_factory,
            credential_handle=self.credential_handle,
            expected_generation=self.expected_generation,
            provider=self.provider,
        )

    def _run(self, method: str, *args: Any, **kwargs: Any) -> Any:
        async def invoke() -> Any:
            async with self._client() as client:
                return await getattr(client, method)(*args, **kwargs)

        return asyncio.run(invoke())

    def chat_completion(self, messages: List[Dict], **kwargs: Any) -> Dict:
        return self._run("chat_completion", messages, **kwargs)

    def chat_completion_stream(self, messages: List[Dict], **kwargs: Any) -> list[Dict]:
        async def invoke() -> list[Dict]:
            async with self._client() as client:
                return [
                    chunk
                    async for chunk in client.chat_completion_stream(messages, **kwargs)
                ]

        return asyncio.run(invoke())

    def embeddings(self, texts: Union[str, List[str]], **kwargs: Any) -> Dict:
        return self._run("embeddings", texts, **kwargs)

    def rerank(self, query: str, passages: List[str], **kwargs: Any) -> Dict:
        return self._run("rerank", query, passages, **kwargs)

    def transcribe(self, audio_data: bytes, **kwargs: Any) -> Dict:
        return self._run("transcribe", audio_data, **kwargs)

    def synthesize(self, text: str, **kwargs: Any) -> bytes:
        return self._run("synthesize", text, **kwargs)

    def generate_image(self, prompt: str, **kwargs: Any) -> Dict:
        return self._run("generate_image", prompt, **kwargs)

    def list_models(self) -> Dict:
        return self._run("list_models")

    def get_recommended_model(self, task: str) -> NVIDIAModel:
        return NVIDIAClient.get_recommended_model(self, task)  # type: ignore[arg-type]


def _raise_for_status(status: int, correlation_id: str) -> None:
    if status < 400:
        return
    if status == 401:
        code = "invalid_auth"
    elif status == 403:
        code = "forbidden_scope"
    elif status == 429:
        code = "rate_limited"
    elif status >= 500:
        code = "provider_unavailable"
    else:
        code = "indeterminate"
    raise ProviderSafeError(code=code, correlation_id=correlation_id)


def _retry_delay(response: Any, attempt: int) -> float:
    value = getattr(response, "headers", {}).get("Retry-After", "")
    try:
        return min(4.0, max(0.25, float(value)))
    except (TypeError, ValueError):
        return 0.5 * (2**attempt)


def _correlation_id() -> str:
    return f"provider-{uuid.uuid4()}"


def _zero(value: bytearray) -> None:
    value[:] = b"\x00" * len(value)


__all__ = ["NVIDIAClient", "SyncNVIDIAClient"]
