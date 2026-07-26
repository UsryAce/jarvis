"""Deterministic, catalog-aware model routing for JARVIS Auto Mode."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


PRIMARY_MODEL = "z-ai/glm-5.2"


@dataclass(frozen=True, slots=True)
class ProviderRoutingMetadata:
    """Secret-free provider state consumed by routing and diagnostics."""

    provider: str
    credential_handle: str | None
    lifecycle_state: str
    generation: int
    validation_category: str | None = None
    catalog_present: bool = False

    @property
    def credential_available(self) -> bool:
        return bool(self.credential_handle) and self.lifecycle_state == "active"


@dataclass(frozen=True)
class RouteDecision:
    """The result of resolving a requested model for a user message."""

    model: str
    task_category: str
    reason: str
    auto_mode: bool
    fallback_used: bool = False
    considered_models: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["considered_models"] = list(self.considered_models)
        # Match the /api/chat field name while retaining ``reason`` for callers
        # that consume RouteDecision directly.
        result["routing_reason"] = self.reason
        return result


class ModelRouter:
    """Choose a strong task-specific chat model from the live NVIDIA catalog.

    Routing is deliberately local and deterministic: no extra inference request is
    needed before the real request, keeping Auto Mode quick and inexpensive.
    """

    PRIMARY_MODEL = PRIMARY_MODEL

    # Ordered by preference. Every list ends in GLM so a usable general model is
    # always preferred over a non-chat endpoint accidentally returned by /models.
    TASK_MODELS: Mapping[str, tuple[str, ...]] = {
        "coding": (
            "deepseek-ai/deepseek-v4-pro",
            "mistralai/codestral-22b-instruct-v0.1",
            "deepseek-ai/deepseek-coder-6.7b-instruct",
            "meta/codellama-70b",
            PRIMARY_MODEL,
        ),
        "reasoning": (
            "nvidia/nemotron-3-ultra-550b-a55b",
            "deepseek-ai/deepseek-v4-pro",
            "qwen/qwen3.5-397b-a17b",
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            PRIMARY_MODEL,
        ),
        "vision_image": (
            "meta/llama-3.2-90b-vision-instruct",
            "meta/llama-4-maverick-17b-128e-instruct",
            "nvidia/nemotron-nano-12b-v2-vl",
            "meta/llama-3.2-11b-vision-instruct",
            PRIMARY_MODEL,
        ),
        # ChatQA is a generative RAG model and therefore works through /chat.
        # Raw embedding-only models are intentionally not sent to /chat/completions.
        "embeddings_retrieval": (
            "nvidia/llama3-chatqa-1.5-70b",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "moonshotai/kimi-k2.6",
            PRIMARY_MODEL,
        ),
        "fast_chat": (
            "meta/llama-3.1-8b-instruct",
            "deepseek-ai/deepseek-v4-flash",
            "openai/gpt-oss-20b",
            "microsoft/phi-3.5-moe-instruct",
            PRIMARY_MODEL,
        ),
        "long_context": (
            "moonshotai/kimi-k2.6",
            "meta/llama-4-maverick-17b-128e-instruct",
            "qwen/qwen3-next-80b-a3b-instruct",
            "mistralai/mistral-large-3-675b-instruct-2512",
            PRIMARY_MODEL,
        ),
        "general": (PRIMARY_MODEL,),
    }

    _PATTERNS: Mapping[str, tuple[str, ...]] = {
        "vision_image": (
            r"\b(?:image|photo|picture|screenshot|diagram|visual|ocr)\b",
            r"\b(?:look at|analy[sz]e|describe|read)\b.{0,30}\b(?:image|photo|screenshot)\b",
        ),
        "embeddings_retrieval": (
            r"\b(?:embedding|embeddings|vector database|vector store|semantic search|rerank|retrieval|rag)\b",
            r"\b(?:retrieve|search)\b.{0,30}\b(?:documents|knowledge base|passages)\b",
        ),
        "coding": (
            r"\b(?:code|coding|program|function|class|api|regex|sql|typescript|javascript|python|rust|golang|java|c\+\+)\b",
            r"\b(?:debug|refactor|compile|implement|unit test|stack trace|exception|repository|codebase)\b",
        ),
        "reasoning": (
            r"\b(?:reason|reasoning|prove|proof|derive|theorem|logic|puzzle|calculate|equation|mathematics?)\b",
            r"\b(?:step[- ]by[- ]step|trade-?offs?|root cause|analy[sz]e deeply|complex problem)\b",
        ),
        "long_context": (
            r"\b(?:long context|entire document|whole document|full document|large document|transcript|book|contract)\b",
            r"\b(?:summari[sz]e|compare|review|extract)\b.{0,40}\b(?:document|report|transcript|files?|chapters?)\b",
        ),
        "fast_chat": (
            r"^(?:hi|hello|hey|thanks|thank you|good morning|good evening)[!,. ]*$",
            r"\b(?:quick|brief|short answer|in one sentence|tldr|tl;dr)\b",
        ),
    }

    _REASONS: Mapping[str, str] = {
        "coding": "Detected a software-development task; selected a code-specialized model.",
        "reasoning": "Detected a multi-step reasoning task; selected a high-capability reasoning model.",
        "vision_image": "Detected an image or visual-understanding task; selected a vision-capable model.",
        "embeddings_retrieval": "Detected a retrieval/RAG task; selected a chat-compatible retrieval specialist.",
        "fast_chat": "Detected a lightweight chat task; selected a fast, efficient model.",
        "long_context": "Detected a long-context task; selected a model suited to large documents.",
        "general": "No specialist category dominated; selected GLM 5.2 as the primary general model.",
    }

    def __init__(
        self, provider_metadata: ProviderRoutingMetadata | None = None
    ) -> None:
        self._provider_metadata = provider_metadata

    @property
    def provider_metadata(self) -> ProviderRoutingMetadata | None:
        return self._provider_metadata

    def update_provider_metadata(self, metadata: ProviderRoutingMetadata) -> None:
        """Replace lifecycle metadata without accepting plaintext/ciphertext."""
        if not isinstance(metadata, ProviderRoutingMetadata):
            raise TypeError("invalid_provider_metadata")
        self._provider_metadata = metadata

    def classify(self, message: str) -> str:
        """Classify a message into one supported routing category."""
        normalized = " ".join((message or "").lower().split())
        for category in (
            "vision_image",
            "embeddings_retrieval",
            "coding",
            "reasoning",
            "long_context",
            "fast_chat",
        ):
            if any(re.search(pattern, normalized) for pattern in self._PATTERNS[category]):
                return category
        return "general"

    @staticmethod
    def normalize_catalog(catalog: Iterable[Any] | None) -> set[str]:
        """Extract model IDs from NVIDIA's model objects or plain ID strings."""
        model_ids: set[str] = set()
        for item in catalog or ():
            if isinstance(item, str):
                model_ids.add(item)
            elif isinstance(item, Mapping) and isinstance(item.get("id"), str):
                model_ids.add(item["id"])
            elif isinstance(getattr(item, "id", None), str):
                model_ids.add(item.id)
        return model_ids

    def route(
        self,
        message: str,
        requested_model: str | None = None,
        available_models: Iterable[Any] | None = None,
        prefer_fast: bool = False,
    ) -> RouteDecision:
        """Resolve explicit/default/auto selection without invoking a model."""
        requested = (requested_model or "").strip()
        if requested and requested.lower() != "auto":
            return RouteDecision(
                model=requested,
                task_category="explicit",
                reason="Using the model explicitly selected by the user.",
                auto_mode=False,
            )

        if not requested:
            return RouteDecision(
                model=self.PRIMARY_MODEL,
                task_category="general",
                reason="Using GLM 5.2, the configured primary model.",
                auto_mode=False,
            )

        category = self.classify(message)
        if prefer_fast and category == "general":
            category = "fast_chat"
        candidates: Sequence[str] = self.TASK_MODELS[category]
        available = self.normalize_catalog(available_models)
        selected = next((model for model in candidates if model in available), None)
        fallback_used = selected is None
        if selected is None:
            selected = self.PRIMARY_MODEL

        reason = self._REASONS[category]
        if fallback_used:
            reason += " No preferred specialist was present in the live catalog, so GLM 5.2 was used safely."
        elif selected != candidates[0]:
            reason += f" The highest-ranked available catalog match was {selected}."

        return RouteDecision(
            model=selected,
            task_category=category,
            reason=reason,
            auto_mode=True,
            fallback_used=fallback_used,
            considered_models=tuple(candidates),
        )
