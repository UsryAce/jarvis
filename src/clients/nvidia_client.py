"""NVIDIA API Client for build.nvidia.com models."""
import asyncio
import base64
import json
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from pathlib import Path

import aiohttp
import httpx

from src.config import config
from src.models.nvidia_models import (
    NVIDIAModel,
    ModelType,
    get_model_by_id,
    get_recommended_chat_models,
    get_recommended_embedding_model,
    get_recommended_reranker,
)


class NVIDIAClient:
    """Async client for NVIDIA API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or config.get("nvidia.api_key") or os.getenv("NVIDIA_API_KEY")
        self.base_url = base_url or config.get("nvidia.api_base", "https://integrate.api.nvidia.com/v1")
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.api_key:
            raise ValueError("NVIDIA API key required. Set NVIDIA_API_KEY env var or in config.")

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session

    # Chat Completion
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        stream: bool = False,
        **kwargs,
    ) -> Dict:
        """Chat completion endpoint."""
        model = model or "meta/llama-3.1-70b-instruct"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": stream,
            **kwargs,
        }

        session = self._get_session()
        async with session.post(f"{self.base_url}/chat/completions", json=payload) as response:
            response.raise_for_status()
            return await response.json()

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        """Stream chat completion."""
        model = model or "meta/llama-3.1-70b-instruct"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }

        session = self._get_session()
        async with session.post(f"{self.base_url}/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.content:
                line = line.decode("utf-8").strip()
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    # Embeddings
    async def embeddings(
        self,
        texts: Union[str, List[str]],
        model: Optional[str] = None,
        input_type: str = "query",
    ) -> Dict:
        """Create embeddings."""
        model = model or get_recommended_embedding_model().id
        if isinstance(texts, str):
            texts = [texts]

        payload = {
            "model": model,
            "input": texts,
            "input_type": input_type,
        }

        session = self._get_session()
        async with session.post(f"{self.base_url}/embeddings", json=payload) as response:
            response.raise_for_status()
            return await response.json()

    # Reranking
    async def rerank(
        self,
        query: str,
        passages: List[str],
        model: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict:
        """Rerank passages for a query."""
        model = model or get_recommended_reranker().id

        payload = {
            "model": model,
            "query": query,
            "passages": passages,
            "top_k": top_k,
        }

        session = self._get_session()
        async with session.post(f"{self.base_url}/rerank", json=payload) as response:
            response.raise_for_status()
            return await response.json()

    # Vision
    async def vision(
        self,
        image_url: str,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Dict:
        """Analyze image with vision model."""
        model = model or "microsoft/phi-3.5-vision-instruct"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        return await self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
        )

    # TTS (Text-to-Speech)
    async def synthesize(
        self,
        text: str,
        model: Optional[str] = None,
        voice: str = "female",
        sample_rate: int = 22050,
    ) -> bytes:
        """Text-to-speech synthesis."""
        model = model or "nvidia/tts_en_us_fastpitch_hifigan"

        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "sample_rate": sample_rate,
        }

        session = self._get_session()
        async with session.post(f"{self.base_url}/audio/speech", json=payload) as response:
            response.raise_for_status()
            return await response.read()

    # STT (Speech-to-Text)
    async def transcribe(
        self,
        audio_data: bytes,
        model: Optional[str] = None,
        language: str = "en",
        response_format: str = "json",
    ) -> Dict:
        """Transcribe audio to text."""
        model = model or "nvidia/stt_en_conformer_transducer_large"

        # Create form data
        form = aiohttp.FormData()
        form.add_field("model", model)
        form.add_field("language", language)
        form.add_field("response_format", response_format)
        form.add_field(
            "file",
            audio_data,
            filename="audio.wav",
            content_type="audio/wav",
        )

        session = self._get_session()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with session.post(
            f"{self.base_url}/audio/transcriptions",
            data=form,
            headers=headers,
        ) as response:
            response.raise_for_status()
            return await response.json()

    # Image Generation
    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        n: int = 1,
        size: str = "1024x1024",
        response_format: str = "url",
    ) -> Dict:
        """Generate image from text prompt."""
        model = model or "stabilityai/stable-diffusion-xl-base-1.0"

        payload = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "response_format": response_format,
        }

        session = self._get_session()
        async with session.post(f"{self.base_url}/images/generations", json=payload) as response:
            response.raise_for_status()
            return await response.json()

    # Model listing
    async def list_models(self) -> Dict:
        """List available models."""
        session = self._get_session()
        async with session.get(f"{self.base_url}/models") as response:
            response.raise_for_status()
            return await response.json()

    # Utility methods
    def get_available_models(self) -> Dict[ModelType, List[NVIDIAModel]]:
        """Get all available models from registry."""
        from src.models.nvidia_models import ALL_MODELS
        return ALL_MODELS

    def get_recommended_model(self, task: str) -> NVIDIAModel:
        """Get recommended model for a task."""
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
        model_id = task_models.get(task, task_models["chat"])
        return get_model_by_id(model_id)


class SyncNVIDIAClient:
    """Synchronous wrapper for NVIDIA API."""

    def __init__(self):
        self.client = None

    def _get_client(self) -> NVIDIAClient:
        if not self.client:
            self.client = NVIDIAClient()
        return self.client

    def chat_completion(self, messages: List[Dict], **kwargs) -> Dict:
        """Synchronous chat completion."""
        return asyncio.run(self._async_chat(messages, **kwargs))

    async def _async_chat(self, messages: List[Dict], **kwargs) -> Dict:
        async with NVIDIAClient() as client:
            return await client.chat_completion(messages, **kwargs)

    def chat_completion_stream(self, messages: List[Dict], **kwargs):
        """Synchronous streaming chat."""
        return asyncio.run(self._async_stream(messages, **kwargs))

    async def _async_stream(self, messages: List[Dict], **kwargs):
        async with NVIDIAClient() as client:
            async for chunk in client.chat_completion_stream(messages, **kwargs):
                yield chunk

    def embeddings(self, texts: Union[str, List[str]], **kwargs) -> Dict:
        """Synchronous embeddings."""
        return asyncio.run(self._async_embeddings(texts, **kwargs))

    async def _async_embeddings(self, texts: Union[str, List[str]], **kwargs) -> Dict:
        async with NVIDIAClient() as client:
            return await client.embeddings(texts, **kwargs)

    def rerank(self, query: str, passages: List[str], **kwargs) -> Dict:
        """Synchronous rerank."""
        return asyncio.run(self._async_rerank(query, passages, **kwargs))

    async def _async_rerank(self, query: str, passages: List[str], **kwargs) -> Dict:
        async with NVIDIAClient() as client:
            return await client.rerank(query, passages, **kwargs)

    def transcribe(self, audio_data: bytes, **kwargs) -> Dict:
        """Synchronous transcribe."""
        return asyncio.run(self._async_transcribe(audio_data, **kwargs))

    async def _async_transcribe(self, audio_data: bytes, **kwargs) -> Dict:
        async with NVIDIAClient() as client:
            return await client.transcribe(audio_data, **kwargs)

    def synthesize(self, text: str, **kwargs) -> bytes:
        """Synchronous synthesize."""
        return asyncio.run(self._async_synthesize(text, **kwargs))

    async def _async_synthesize(self, text: str, **kwargs) -> bytes:
        async with NVIDIAClient() as client:
            return await client.synthesize(text, **kwargs)

    def generate_image(self, prompt: str, **kwargs) -> Dict:
        """Synchronous image generation."""
        return asyncio.run(self._async_generate_image(prompt, **kwargs))

    async def _async_generate_image(self, prompt: str, **kwargs) -> Dict:
        async with NVIDIAClient() as client:
            return await client.generate_image(prompt, **kwargs)

    def list_models(self) -> Dict:
        """Synchronous list models."""
        return asyncio.run(self._async_list_models())

    async def _async_list_models(self) -> Dict:
        async with NVIDIAClient() as client:
            return await client.list_models()

    def get_recommended_model(self, task: str) -> NVIDIAModel:
        """Get recommended model for task."""
        return NVIDIAClient().get_recommended_model(task)