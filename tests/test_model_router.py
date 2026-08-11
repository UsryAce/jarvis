"""Focused tests for deterministic JARVIS Auto Mode routing."""

from src.core.model_router import PRIMARY_MODEL, ModelRouter


def test_default_model_is_glm_52():
    decision = ModelRouter().route("Hello")

    assert decision.model == PRIMARY_MODEL
    assert decision.auto_mode is False
    assert decision.task_category == "general"


def test_explicit_model_is_preserved_even_if_not_in_catalog():
    decision = ModelRouter().route(
        "Write some Python",
        requested_model="vendor/my-explicit-model",
        available_models=[PRIMARY_MODEL],
    )

    assert decision.model == "vendor/my-explicit-model"
    assert decision.task_category == "explicit"
    assert decision.auto_mode is False


def test_auto_coding_selects_available_code_specialist():
    decision = ModelRouter().route(
        "Debug this Python exception and write unit tests",
        requested_model="auto",
        available_models=[
            {"id": PRIMARY_MODEL},
            {"id": "mistralai/codestral-22b-instruct-v0.1"},
            {"id": "deepseek-ai/deepseek-v4-pro"},
        ],
    )

    assert decision.task_category == "coding"
    assert decision.model == "deepseek-ai/deepseek-v4-pro"
    assert decision.auto_mode is True


def test_auto_uses_highest_ranked_model_that_is_actually_available():
    decision = ModelRouter().route(
        "Prove this theorem step-by-step",
        requested_model="AUTO",
        available_models=[PRIMARY_MODEL, "qwen/qwen3.5-397b-a17b"],
    )

    assert decision.task_category == "reasoning"
    assert decision.model == "qwen/qwen3.5-397b-a17b"
    assert "highest-ranked available" in decision.reason


def test_visual_task_has_priority_over_generic_analysis_language():
    decision = ModelRouter().route(
        "Analyze this screenshot and describe the UI",
        requested_model="auto",
        available_models=[PRIMARY_MODEL, "meta/llama-3.2-90b-vision-instruct"],
    )

    assert decision.task_category == "vision_image"
    assert decision.model == "meta/llama-3.2-90b-vision-instruct"


def test_retrieval_routes_to_chat_compatible_rag_model_not_embedding_endpoint():
    decision = ModelRouter().route(
        "Use RAG and semantic search over my knowledge base",
        requested_model="auto",
        available_models=[
            "nvidia/nv-embedqa-e5-v5",
            "nvidia/llama3-chatqa-1.5-70b",
            PRIMARY_MODEL,
        ],
    )

    assert decision.task_category == "embeddings_retrieval"
    assert decision.model == "nvidia/llama3-chatqa-1.5-70b"


def test_auto_falls_back_safely_when_catalog_is_empty():
    decision = ModelRouter().route(
        "Implement a TypeScript API",
        requested_model="auto",
        available_models=[],
    )

    assert decision.model == PRIMARY_MODEL
    assert decision.fallback_used is True
    assert "safely" in decision.reason


def test_preview_payload_is_json_friendly():
    decision = ModelRouter().route(
        "Give me a quick answer",
        requested_model="auto",
        available_models=[PRIMARY_MODEL, "deepseek-ai/deepseek-v4-flash"],
    )

    payload = decision.to_dict()
    assert payload["model"] == "deepseek-ai/deepseek-v4-flash"
    assert payload["task_category"] == "fast_chat"
    assert payload["routing_reason"] == payload["reason"]
    assert isinstance(payload["considered_models"], list)


def test_voice_mode_prefers_fast_model_for_general_conversation():
    decision = ModelRouter().route(
        "Tell me whether the system is ready",
        requested_model="auto",
        available_models=[PRIMARY_MODEL, "meta/llama-3.1-8b-instruct"],
        prefer_fast=True,
    )

    assert decision.task_category == "fast_chat"
    assert decision.model == "meta/llama-3.1-8b-instruct"


def test_voice_mode_keeps_specialist_routing_for_code_tasks():
    decision = ModelRouter().route(
        "Debug this Python function",
        requested_model="auto",
        available_models=[PRIMARY_MODEL, "meta/llama-3.1-8b-instruct", "deepseek-ai/deepseek-v4-pro"],
        prefer_fast=True,
    )

    assert decision.task_category == "coding"
    assert decision.model == "deepseek-ai/deepseek-v4-pro"
