"""NVIDIA Models Registry - https://build.nvidia.com/models
Based on actual API availability as of 2026.
Working models confirmed via API testing with multiple keys.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ModelType(Enum):
    CHAT = "chat"
    EMBEDDING = "embedding"
    RERANKING = "reranking"
    VISION = "vision"
    TTS = "tts"
    STT = "stt"
    MULTIMODAL = "multimodal"


@dataclass
class NVIDIAModel:
    id: str
    name: str
    model_type: ModelType
    description: str
    context_window: int
    max_output: int
    pricing: Optional[str] = None
    tags: Optional[List[str]] = None
    deprecated: bool = False
    confirmed_working: bool = False


# CONFIRMED WORKING Chat Models (tested via API)
WORKING_CHAT_MODELS = [
    NVIDIAModel(
        id="meta/llama-3.1-70b-instruct",
        name="Llama 3.1 70B Instruct",
        model_type=ModelType.CHAT,
        description="Meta's 70B parameter Llama 3.1 model - CONFIRMED WORKING. Excellent balance of quality and speed for general tasks, coding, reasoning.",
        context_window=128000,
        max_output=4096,
        tags=["confirmed", "balanced", "multilingual", "coding", "reasoning"],
        confirmed_working=True,
    ),
    NVIDIAModel(
        id="meta/llama-3.1-8b-instruct",
        name="Llama 3.1 8B Instruct",
        model_type=ModelType.CHAT,
        description="Meta's lightweight 8B Llama 3.1 model - CONFIRMED WORKING. Fast and efficient for quick responses.",
        context_window=128000,
        max_output=4096,
        tags=["confirmed", "fast", "lightweight", "multilingual"],
        confirmed_working=True,
    ),
    NVIDIAModel(
        id="upstage/solar-10.7b-instruct",
        name="Solar 10.7B Instruct",
        model_type=ModelType.CHAT,
        description="Upstage's Solar 10.7B model - CONFIRMED WORKING. Efficient and capable Korean/English bilingual model.",
        context_window=4096,
        max_output=4096,
        tags=["confirmed", "efficient", "korean", "bilingual"],
        confirmed_working=True,
    ),
]

# HIGH PRIORITY - Likely Working (from model list, need testing)
HIGH_PRIORITY_CHAT_MODELS = [
    NVIDIAModel(
        id="meta/llama-3.1-405b-instruct",
        name="Llama 3.1 405B Instruct",
        model_type=ModelType.CHAT,
        description="Meta's largest Llama 3.1 model with 405B parameters. State-of-the-art open model for complex reasoning.",
        context_window=128000,
        max_output=4096,
        tags=["largest", "reasoning", "multilingual", "flagship"],
    ),
    NVIDIAModel(
        id="meta/llama-3.2-11b-vision-instruct",
        name="Llama 3.2 11B Vision Instruct",
        model_type=ModelType.MULTIMODAL,
        description="Meta's Llama 3.2 with vision capabilities. 11B parameters, handles images + text.",
        context_window=128000,
        max_output=4096,
        tags=["vision", "multimodal", "llama32"],
    ),
    NVIDIAModel(
        id="meta/llama-3.2-90b-vision-instruct",
        name="Llama 3.2 90B Vision Instruct",
        model_type=ModelType.MULTIMODAL,
        description="Meta's largest Llama 3.2 vision model. 90B parameters for complex visual reasoning.",
        context_window=128000,
        max_output=4096,
        tags=["vision", "multimodal", "flagship", "llama32"],
    ),
    NVIDIAModel(
        id="meta/llama-3.3-70b-instruct",
        name="Llama 3.3 70B Instruct",
        model_type=ModelType.CHAT,
        description="Meta's improved Llama 3.3 70B model. Better reasoning and instruction following.",
        context_window=128000,
        max_output=4096,
        tags=["improved", "reasoning", "llama33"],
    ),
    NVIDIAModel(
        id="meta/llama-4-maverick-17b-128e-instruct",
        name="Llama 4 Maverick 17B 128E Instruct",
        model_type=ModelType.CHAT,
        description="Meta's Llama 4 Maverick with mixture-of-experts architecture. 17B active, 128B total params.",
        context_window=128000,
        max_output=4096,
        tags=["moe", "llama4", "efficient"],
    ),
    NVIDIAModel(
        id="z-ai/glm-5.2",
        name="GLM-5.2",
        model_type=ModelType.CHAT,
        description="Z.ai's GLM 5.2 model. Strong in Chinese and English, excellent reasoning capabilities.",
        context_window=128000,
        max_output=4096,
        tags=["glm5", "chinese", "reasoning", "flagship"],
    ),
    NVIDIAModel(
        id="moonshotai/kimi-k2.6",
        name="Kimi K2.6",
        model_type=ModelType.CHAT,
        description="Moonshot AI's Kimi K2.6. Large context window, strong long-form reasoning.",
        context_window=128000,
        max_output=4096,
        tags=["kimi", "long-context", "reasoning"],
    ),
    NVIDIAModel(
        id="mistralai/mistral-large",
        name="Mistral Large",
        model_type=ModelType.CHAT,
        description="Mistral AI's flagship large model. Excellent reasoning, coding, and multilingual support.",
        context_window=128000,
        max_output=4096,
        tags=["mistral", "flagship", "reasoning", "code"],
    ),
    NVIDIAModel(
        id="mistralai/mistral-large-2-instruct",
        name="Mistral Large 2 Instruct",
        model_type=ModelType.CHAT,
        description="Mistral Large 2 - improved version with better instruction following.",
        context_window=128000,
        max_output=4096,
        tags=["mistral", "v2", "reasoning", "code"],
    ),
    NVIDIAModel(
        id="mistralai/mistral-nemo-12b-instruct",
        name="Mistral NeMo 12B Instruct",
        model_type=ModelType.CHAT,
        description="Mistral AI's 12B model co-trained with NVIDIA. Optimized for NVIDIA hardware.",
        context_window=128000,
        max_output=4096,
        tags=["mistral", "nvidia", "optimized", "multilingual"],
    ),
    NVIDIAModel(
        id="nv-mistralai/mistral-nemo-12b-instruct",
        name="NVIDIA Mistral NeMo 12B",
        model_type=ModelType.CHAT,
        description="NVIDIA-optimized version of Mistral NeMo 12B.",
        context_window=128000,
        max_output=4096,
        tags=["nvidia", "mistral", "optimized"],
    ),
    NVIDIAModel(
        id="qwen/qwen3-next-80b-a3b-instruct",
        name="Qwen 3 Next 80B-A3B",
        model_type=ModelType.CHAT,
        description="Alibaba's Qwen 3 Next with mixture-of-experts. 80B total, 3B active params.",
        context_window=128000,
        max_output=4096,
        tags=["qwen", "moe", "multilingual", "chinese"],
    ),
    NVIDIAModel(
        id="deepseek-ai/deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        model_type=ModelType.CHAT,
        description="DeepSeek's flagship V4 Pro model. Strong reasoning and coding capabilities.",
        context_window=128000,
        max_output=4096,
        tags=["deepseek", "v4", "reasoning", "coding", "flagship"],
    ),
    NVIDIAModel(
        id="deepseek-ai/deepseek-coder-6.7b-instruct",
        name="DeepSeek Coder 6.7B Instruct",
        model_type=ModelType.CHAT,
        description="DeepSeek's specialized coding model. Excellent for code generation and debugging.",
        context_window=128000,
        max_output=4096,
        tags=["coding", "specialized", "deepseek"],
    ),
    NVIDIAModel(
        id="microsoft/phi-4-mini-instruct",
        name="Phi-4 Mini Instruct",
        model_type=ModelType.CHAT,
        description="Microsoft's Phi-4 mini model. Compact but powerful for edge deployment.",
        context_window=128000,
        max_output=4096,
        tags=["phi4", "compact", "edge", "fast"],
    ),
    NVIDIAModel(
        id="microsoft/phi-4-multimodal-instruct",
        name="Phi-4 Multimodal Instruct",
        model_type=ModelType.MULTIMODAL,
        description="Microsoft's Phi-4 with vision and audio capabilities.",
        context_window=128000,
        max_output=4096,
        tags=["phi4", "multimodal", "vision", "audio"],
    ),
    NVIDIAModel(
        id="google/gemma-3-12b-it",
        name="Gemma 3 12B IT",
        model_type=ModelType.CHAT,
        description="Google's Gemma 3 12B instruction-tuned. Improved over Gemma 2.",
        context_window=128000,
        max_output=4096,
        tags=["gemma3", "google", "multilingual"],
    ),
    NVIDIAModel(
        id="google/gemma-3-4b-it",
        name="Gemma 3 4B IT",
        model_type=ModelType.CHAT,
        description="Google's Gemma 3 4B. Compact and efficient.",
        context_window=128000,
        max_output=4096,
        tags=["gemma3", "compact", "google"],
    ),
    NVIDIAModel(
        id="google/codegemma-7b",
        name="CodeGemma 7B",
        model_type=ModelType.CHAT,
        description="Google's CodeGemma 7B. Specialized for code generation.",
        context_window=8192,
        max_output=4096,
        tags=["coding", "gemma", "google"],
    ),
    NVIDIAModel(
        id="writer/palmyra-creative-122b",
        name="Palmyra Creative 122B",
        model_type=ModelType.CHAT,
        description="Writer's Palmyra Creative 122B. Optimized for creative writing and content.",
        context_window=128000,
        max_output=4096,
        tags=["creative", "writing", "palmyra"],
    ),
    NVIDIAModel(
        id="writer/palmyra-fin-70b-32k",
        name="Palmyra Fin 70B 32K",
        model_type=ModelType.CHAT,
        description="Writer's Palmyra Fin 70B. Specialized for financial analysis and reporting.",
        context_window=32768,
        max_output=4096,
        tags=["finance", "financial", "analysis", "palmyra"],
    ),
    NVIDIAModel(
        id="stepfun-ai/step-3.7-flash",
        name="Step 3.7 Flash",
        model_type=ModelType.CHAT,
        description="StepFun's Step 3.7 Flash. Fast and efficient model.",
        context_window=128000,
        max_output=4096,
        tags=["fast", "efficient", "stepfun"],
    ),
]

# Embedding Models (from model list)
EMBEDDING_MODELS = [
    NVIDIAModel(
        id="nvidia/nv-embedqa-e5-v5",
        name="NV-Embed-QA-E5-v5",
        model_type=ModelType.EMBEDDING,
        description="NVIDIA's state-of-the-art embedding model for QA and retrieval. CONFIRMED in model list.",
        context_window=8192,
        max_output=1024,
        tags=["qa", "retrieval", "sota"],
    ),
    NVIDIAModel(
        id="nvidia/nv-embedqa-mistral-7b-v2",
        name="NV-Embed-QA-Mistral-7B-v2",
        model_type=ModelType.EMBEDDING,
        description="NVIDIA's Mistral-7B based embedding for QA retrieval.",
        context_window=8192,
        max_output=4096,
        tags=["qa", "retrieval", "mistral"],
    ),
    NVIDIAModel(
        id="nvidia/nv-embed-v1",
        name="NV-Embed v1",
        model_type=ModelType.EMBEDDING,
        description="NVIDIA's general-purpose embedding model.",
        context_window=8192,
        max_output=4096,
        tags=["general", "retrieval"],
    ),
    NVIDIAModel(
        id="nvidia/nv-embedcode-7b-v1",
        name="NV-EmbedCode 7B v1",
        model_type=ModelType.EMBEDDING,
        description="NVIDIA's code-specialized embedding model.",
        context_window=8192,
        max_output=4096,
        tags=["code", "embedding", "specialized"],
    ),
    NVIDIAModel(
        id="nvidia/llama-3.2-nv-embedqa-1b-v1",
        name="Llama 3.2 NV-EmbedQA 1B v1",
        model_type=ModelType.EMBEDDING,
        description="NVIDIA's Llama 3.2 based compact embedding model.",
        context_window=8192,
        max_output=1024,
        tags=["compact", "llama32", "qa"],
    ),
    NVIDIAModel(
        id="nvidia/llama-nemotron-embed-1b-v2",
        name="Llama Nemotron Embed 1B v2",
        model_type=ModelType.EMBEDDING,
        description="NVIDIA's Nemotron-based compact embedding model.",
        context_window=8192,
        max_output=1024,
        tags=["compact", "nemotron", "embedding"],
    ),
    NVIDIAModel(
        id="baai/bge-m3",
        name="BGE-M3",
        model_type=ModelType.EMBEDDING,
        description="BAAI's multilingual embedding model with multi-granularity.",
        context_window=8192,
        max_output=1024,
        tags=["multilingual", "multigranular", "retrieval"],
    ),
    NVIDIAModel(
        id="snowflake/arctic-embed-l",
        name="Arctic Embed L",
        model_type=ModelType.EMBEDDING,
        description="Snowflake's Arctic Embed Large. High-quality retrieval embeddings.",
        context_window=8192,
        max_output=1024,
        tags=["snowflake", "retrieval", "large"],
    ),
    NVIDIAModel(
        id="intfloat/multilingual-e5-large",
        name="Multilingual E5 Large",
        model_type=ModelType.EMBEDDING,
        description="Intfloat's multilingual E5 Large embedding model.",
        context_window=512,
        max_output=1024,
        tags=["multilingual", "retrieval"],
    ),
]

# Reranking Models
RERANKING_MODELS = [
    NVIDIAModel(
        id="nvidia/nv-rerank-qa-mistral-4b-v3",
        name="NV-Rerank-QA-Mistral-4B-v3",
        model_type=ModelType.RERANKING,
        description="NVIDIA's QA-optimized reranker based on Mistral 4B.",
        context_window=8192,
        max_output=1,
        tags=["qa", "reranking", "mistral"],
    ),
    NVIDIAModel(
        id="nvidia/llama-3.1-nemotron-70b-rerank",
        name="Nemotron 3 Ultra Rerank",
        model_type=ModelType.RERANKING,
        description="Nemotron 3 Ultra adapted for reranking tasks.",
        context_window=128000,
        max_output=1,
        tags=["reranking", "nemotron"],
    ),
]

# Vision Models
VISION_MODELS = [
    NVIDIAModel(
        id="meta/llama-3.2-90b-vision-instruct",
        name="Llama 3.2 90B Vision Instruct",
        model_type=ModelType.VISION,
        description="Meta's largest Llama 3.2 vision model. 90B parameters for complex visual reasoning.",
        context_window=128000,
        max_output=4096,
        tags=["vision", "multimodal", "flagship", "llama32"],
    ),
    NVIDIAModel(
        id="meta/llama-3.2-11b-vision-instruct",
        name="Llama 3.2 11B Vision Instruct",
        model_type=ModelType.VISION,
        description="Meta's Llama 3.2 with vision capabilities. 11B parameters.",
        context_window=128000,
        max_output=4096,
        tags=["vision", "multimodal", "llama32"],
    ),
    NVIDIAModel(
        id="microsoft/phi-4-multimodal-instruct",
        name="Phi-4 Multimodal Instruct",
        model_type=ModelType.MULTIMODAL,
        description="Microsoft's Phi-4 with vision and audio capabilities.",
        context_window=128000,
        max_output=4096,
        tags=["phi4", "multimodal", "vision", "audio"],
    ),
]

# TTS Models
TTS_MODELS = [
    NVIDIAModel(
        id="nvidia/tts_en_us_fastpitch_hifigan",
        name="FastPitch HiFi-GAN English US",
        model_type=ModelType.TTS,
        description="NVIDIA's FastPitch with HiFi-GAN vocoder for English US.",
        context_window=1024,
        max_output=1024,
        tags=["tts", "english", "fastpitch", "hifigan"],
    ),
]

# STT Models
STT_MODELS = [
    NVIDIAModel(
        id="nvidia/stt_en_conformer_transducer_large",
        name="Conformer Transducer Large English",
        model_type=ModelType.STT,
        description="NVIDIA's Conformer-Transducer large model for English ASR.",
        context_window=1024,
        max_output=1024,
        tags=["stt", "asr", "english", "conformer"],
    ),
]

ALL_MODELS = {
    ModelType.CHAT: WORKING_CHAT_MODELS + HIGH_PRIORITY_CHAT_MODELS,
    ModelType.EMBEDDING: EMBEDDING_MODELS,
    ModelType.RERANKING: RERANKING_MODELS,
    ModelType.VISION: VISION_MODELS,
    ModelType.TTS: TTS_MODELS,
    ModelType.STT: STT_MODELS,
}


def get_models_by_type(model_type: ModelType) -> List[NVIDIAModel]:
    """Get all models of a specific type."""
    return ALL_MODELS.get(model_type, [])


def get_working_chat_models() -> List[NVIDIAModel]:
    """Get confirmed working chat models."""
    return [m for m in WORKING_CHAT_MODELS if m.confirmed_working]


def get_high_priority_chat_models() -> List[NVIDIAModel]:
    """Get high priority chat models to test."""
    return HIGH_PRIORITY_CHAT_MODELS


def get_model_by_id(model_id: str) -> Optional[NVIDIAModel]:
    """Find a model by its ID."""
    for models in ALL_MODELS.values():
        for model in models:
            if model.id == model_id:
                return model
    # Check working models
    for model in WORKING_CHAT_MODELS:
        if model.id == model_id:
            return model
    # Check high priority
    for model in HIGH_PRIORITY_CHAT_MODELS:
        if model.id == model_id:
            return model
    return None


def get_recommended_chat_models() -> List[NVIDIAModel]:
    """Get recommended chat models for different use cases."""
    return [
        # Confirmed working
        get_model_by_id("meta/llama-3.1-70b-instruct"),      # Best overall confirmed
        get_model_by_id("meta/llama-3.1-8b-instruct"),       # Fast confirmed
        get_model_by_id("upstage/solar-10.7b-instruct"),     # Efficient confirmed
        # High priority to test
        get_model_by_id("z-ai/glm-5.2"),                      # GLM 5.2
        get_model_by_id("moonshotai/kimi-k2.6"),              # Kimi K2.6
        get_model_by_id("meta/llama-3.1-405b-instruct"),      # Largest
        get_model_by_id("mistralai/mistral-large"),           # Mistral flagship
        get_model_by_id("deepseek-ai/deepseek-coder-6.7b-instruct"), # Best for coding
        get_model_by_id("microsoft/phi-4-mini-instruct"),     # Best for edge
        get_model_by_id("writer/palmyra-fin-70b-32k"),        # Best for finance
    ]


def get_recommended_embedding_model() -> NVIDIAModel:
    """Get recommended embedding model."""
    return get_model_by_id("nvidia/nv-embedqa-e5-v5") or EMBEDDING_MODELS[0]


def get_recommended_reranker() -> NVIDIAModel:
    """Get recommended reranker."""
    return get_model_by_id("nvidia/nv-rerank-qa-mistral-4b-v3") or RERANKING_MODELS[0]


def get_recommended_vision_model() -> NVIDIAModel:
    """Get recommended vision model."""
    return get_model_by_id("meta/llama-3.2-90b-vision-instruct") or VISION_MODELS[0]


def get_recommended_multimodal_model() -> NVIDIAModel:
    """Get recommended multimodal model."""
    return get_model_by_id("meta/llama-3.2-11b-vision-instruct")


# Model categories for specific use cases
MODEL_RECOMMENDATIONS = {
    "general_best": ["meta/llama-3.1-70b-instruct", "meta/llama-3.1-405b-instruct", "z-ai/glm-5.2"],
    "fast": ["meta/llama-3.1-8b-instruct", "microsoft/phi-4-mini-instruct", "upstage/solar-10.7b-instruct"],
    "coding": ["deepseek-ai/deepseek-coder-6.7b-instruct", "google/codegemma-7b", "meta/llama-3.1-70b-instruct"],
    "reasoning": ["meta/llama-3.1-405b-instruct", "z-ai/glm-5.2", "mistralai/mistral-large"],
    "finance": ["writer/palmyra-fin-70b-32k", "meta/llama-3.1-70b-instruct"],
    "creative": ["writer/palmyra-creative-122b", "meta/llama-3.1-70b-instruct"],
    "vision": ["meta/llama-3.2-90b-vision-instruct", "meta/llama-3.2-11b-vision-instruct"],
    "multimodal": ["microsoft/phi-4-multimodal-instruct", "meta/llama-3.2-11b-vision-instruct"],
    "edge": ["microsoft/phi-4-mini-instruct", "meta/llama-3.2-1b-instruct", "google/gemma-3-4b-it"],
    "long_context": ["moonshotai/kimi-k2.6", "meta/llama-3.1-405b-instruct", "writer/palmyra-fin-70b-32k"],
    "korean": ["upstage/solar-10.7b-instruct"],
    "chinese": ["z-ai/glm-5.2", "qwen/qwen3-next-80b-a3b-instruct", "01-ai/yi-large"],
}