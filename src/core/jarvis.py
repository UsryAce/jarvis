"""Core Jarvis orchestrator."""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from pathlib import Path

from src.config import config
from src.clients.nvidia_client import NVIDIAClient, SyncNVIDIAClient
from src.memory.vector_memory import VectorMemory
from src.skills.registry import SkillRegistry
from src.core.model_router import ModelRouter, RouteDecision
from src.core.agent import AgentRuntime
from src.core.audit import AuditService
from src.core.control import ControlBlockedError, ControlService, ControlSnapshot, ControlState
from src.core.control_store import ControlStore
from src.core.swarm import MultiAgentOrchestrator
from src.core.workspaces import WorkspaceRegistry
from src.security.auth import SessionService

logger = logging.getLogger(__name__)


class Jarvis:
    """Main Jarvis orchestrator."""

    def __init__(
        self,
        *,
        control_store: ControlStore | None = None,
        audit_service: AuditService | None = None,
        session_service: SessionService | None = None,
        control_service: ControlService | None = None,
    ):
        self.control_store = control_store
        self.audit_service = audit_service
        self.session_service = session_service
        self.control_service = control_service
        self.control_snapshot: ControlSnapshot | None = (
            control_service.snapshot() if control_service is not None else None
        )
        self.trust_status = "verified" if control_service is not None else "legacy"
        self.nvidia_client: Optional[NVIDIAClient] = None
        self.sync_client = SyncNVIDIAClient()
        self.memory: Optional[VectorMemory] = None
        self.skills = SkillRegistry()
        self.conversation_history: List[Dict] = []
        self.system_prompt = self._get_system_prompt()
        self.model_router = ModelRouter()
        # Global stop truth is loaded above before either recovery-capable runtime exists.
        self.agent_runtime = AgentRuntime(self, control_service=control_service)
        project_root = Path(__file__).resolve().parents[2]
        self.workspace_registry = WorkspaceRegistry(
            Path(config.get("swarm.workspace_database", str(project_root / "data" / "workspaces.db"))),
            self.agent_runtime.workspace_root,
        )
        self.swarm_runtime = MultiAgentOrchestrator(
            self, max_concurrency=int(config.get("swarm.max_agents", 8)),
            workspace_registry=self.workspace_registry,
            control_service=control_service,
        )
        self._model_catalog: set[str] = set()
        self._model_catalog_cached_at = 0.0
        self._initialized = False

    def _get_system_prompt(self) -> str:
        """Get system prompt for Jarvis."""
        return """You are JARVIS, Ahmed's advanced personal AI assistant with an original cinematic science-fiction identity.
You are intelligent, helpful, witty, and professional.
Ahmed is your operator. Address him as Ahmed when it is natural and never call him Tony Stark.

Capabilities:
- Natural language understanding and generation
- Code generation, analysis, and debugging
- Web search and research
- File operations and system control
- Memory and context management
- Voice interaction (speech-to-text and text-to-speech)
- Image analysis and generation
- Task planning and execution
- Skill-based extensibility

Personality:
- Professional yet personable
- Concise but thorough when needed
- Proactive in offering help
- Honest about limitations
- Witty with a dry sense of humor

Guidelines:
- Always be helpful and accurate
- Ask clarifying questions when needed
- Provide actionable solutions
- Respect user privacy and security
- Admit when you don't know something
- Offer alternatives when you can't do something directly"""

    async def initialize(self):
        """Initialize Jarvis components."""
        if self._initialized:
            return

        logger.info("Initializing JARVIS...")

        if self.control_store is not None:
            # Re-run integrity/audit verification immediately before any provider,
            # recovery worker, scheduler, or skill can perform an effect.
            with self.control_store._lock:
                self.control_store._verify_database(
                    self.control_store._require_connection(), verify_audit=True
                )
            if self.audit_service is None or not self.audit_service.verify_chain().valid:
                self.trust_status = "integrity_locked"
                raise RuntimeError("audit_integrity_invalid")
            if self.control_service is None:
                self.trust_status = "integrity_locked"
                raise RuntimeError("control_service_unavailable")
            self.control_snapshot = self.control_service.snapshot()
            self.trust_status = "verified"
            if self.control_snapshot.state is not ControlState.RUNNING:
                # Keep protected control/reset authority available at the API layer,
                # but do not warm providers or start recovery-capable runtimes.
                self.trust_status = self.control_snapshot.state.value
                logger.warning(
                    "JARVIS runtime start blocked by durable control revision %s",
                    self.control_snapshot.revision,
                )
                return

        # Initialize NVIDIA client
        # Keep one HTTP session warm for model catalog and chat requests.  Creating
        # a session per turn forced a fresh DNS/TCP/TLS setup before every reply,
        # which is especially noticeable in the voice interface.
        self.nvidia_client = NVIDIAClient()
        await self.nvidia_client.__aenter__()

        # Initialize memory
        self.memory = VectorMemory()
        await self.memory.initialize()

        # Load skills
        await self.skills.load_skills(config.get("skills.enabled", []))

        # Load conversation history
        await self._load_history()

        # Start the durable autonomous worker and recover unfinished goals.
        await self.agent_runtime.start()
        await self.swarm_runtime.start()

        self._initialized = True
        logger.info("JARVIS initialized successfully")

    async def _load_history(self):
        """Load conversation history from memory."""
        try:
            history = await self.memory.get_conversation_history(limit=50)
            # Convert history format to standard message format
            self.conversation_history = []
            for item in history:
                if "user_msg" in item:
                    self.conversation_history.append({
                        "role": "user",
                        "content": item["user_msg"],
                        "timestamp": item.get("timestamp", "")
                    })
                if "assistant_msg" in item:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": item["assistant_msg"],
                        "timestamp": item.get("timestamp", "")
                    })
        except Exception as e:
            logger.warning(f"Could not load history: {e}")

    async def chat(
        self,
        message: str,
        stream: bool = False,
        use_memory: bool = True,
        use_skills: bool = True,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        interaction_mode: str = "chat",
    ) -> AsyncGenerator[str, None] | str:
        """Main chat interface."""
        if not self._initialized:
            await self.initialize()
        self._require_runtime_effect("provider")

        voice_mode = interaction_mode.strip().lower() == "voice"
        routing = await self.route_model(message, model, prefer_fast=voice_mode)
        resolved_model = routing.model

        # Voice conversations already carry the recent transcript below.  Avoid a
        # remote embedding round-trip unless Ahmed explicitly asks to recall older
        # information, and keep spoken answers compact so TTS can start sooner.
        if voice_mode:
            use_memory = use_memory and self._voice_needs_long_term_memory(message)
            max_tokens = min(max_tokens, 192)

        # Add user message to history
        user_msg = {"role": "user", "content": message, "timestamp": datetime.now().isoformat()}
        self.conversation_history.append(user_msg)

        async def find_memories() -> list[dict]:
            if not use_memory or not self.memory:
                return []
            return await self.memory.search(message, limit=5)

        async def run_skills() -> str:
            if not use_skills:
                return ""
            return await self.skills.execute_if_applicable(message, self)

        memories, skill_results = await asyncio.gather(find_memories(), run_skills())
        context = ""
        if memories:
            context = "\nRelevant memories:\n" + "\n".join(
                [f"- {m['content']}" for m in memories]
            )

        # A matched skill has already computed the factual result.  In voice mode,
        # speak that result directly instead of sending it through a second model
        # call (which previously made simple requests such as "what time is it"
        # wait on an occasionally cold inference worker for 3-30 seconds).
        if voice_mode and skill_results:
            direct_response = skill_results.split("] ", 1)[-1].strip()
            assistant_msg = {
                "role": "assistant",
                "content": direct_response,
                "timestamp": datetime.now().isoformat(),
            }
            self.conversation_history.append(assistant_msg)
            if self.memory:
                asyncio.create_task(self._save_conversation(message, direct_response))
            if stream:
                return self._stream_text(direct_response)
            return direct_response

        # Build messages
        system_content = self.system_prompt + context
        if voice_mode:
            system_content += (
                "\nVoice response mode: answer immediately and conversationally. "
                "Use at most three short sentences unless Ahmed explicitly asks for detail."
            )
        messages = [{"role": "system", "content": system_content}]
        
        # Include conversation history
        messages.extend(self.conversation_history[-12:])
        
        # Add skill results as a separate message if available
        if skill_results:
            messages.append({"role": "user", "content": f"[System: Tool results for your query]\n{skill_results}\n[End of tool results]"})
        
        # Get response
        if stream:
            return self._stream_response(messages, resolved_model, message, max_tokens)
        else:
            return await self._get_response(messages, resolved_model, message, max_tokens)

    @staticmethod
    def _voice_needs_long_term_memory(message: str) -> bool:
        """Only pay the remote memory lookup cost for explicit recall requests."""
        normalized = " ".join((message or "").lower().split())
        recall_phrases = (
            "remember",
            "do you recall",
            "what did i",
            "what have i",
            "last time",
            "previous conversation",
            "we discussed",
            "you told me",
            "i told you",
        )
        return any(phrase in normalized for phrase in recall_phrases)

    @staticmethod
    async def _stream_text(text: str) -> AsyncGenerator[str, None]:
        """Expose an already-computed local result through the normal SSE path."""
        if text:
            yield text

    async def route_model(
        self, message: str, requested_model: Optional[str] = None, prefer_fast: bool = False
    ) -> RouteDecision:
        """Resolve a requested model, consulting the live catalog for Auto Mode."""
        self._require_runtime_effect("provider")
        requested = (requested_model or "").strip()
        if requested.lower() != "auto":
            return self.model_router.route(message, requested_model)

        models = await self._get_live_model_catalog()
        return self.model_router.route(message, requested_model, models, prefer_fast=prefer_fast)

    async def _get_live_model_catalog(self, ttl_seconds: int = 300) -> set[str]:
        """Return cached live NVIDIA model IDs, retaining a safe stale cache on errors."""
        now = time.monotonic()
        if self._model_catalog and now - self._model_catalog_cached_at < ttl_seconds:
            return set(self._model_catalog)

        try:
            if self.nvidia_client is not None:
                catalog = await self.nvidia_client.list_models()
            else:
                async with NVIDIAClient() as client:
                    catalog = await client.list_models()
            model_ids = self.model_router.normalize_catalog(catalog.get("data", []))
            if model_ids:
                self._model_catalog = model_ids
                self._model_catalog_cached_at = now
        except Exception as exc:
            logger.warning("Could not refresh NVIDIA model catalog for Auto Mode: %s", exc)

        return set(self._model_catalog)

    async def _get_response(
        self, messages: List[Dict], model: Optional[str], user_message: str, max_tokens: int
    ) -> str:
        """Get non-streaming response."""
        if self.nvidia_client is not None:
            response = await self.nvidia_client.chat_completion(
                messages, model=model, max_tokens=max_tokens
            )
        else:
            async with NVIDIAClient() as client:
                response = await client.chat_completion(messages, model=model, max_tokens=max_tokens)
        content = response["choices"][0]["message"]["content"]

        # Save to history
        assistant_msg = {
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversation_history.append(assistant_msg)

        # Save to memory
        if self.memory:
            asyncio.create_task(self._save_conversation(user_message, content))

        return content

    async def _stream_response(
        self, messages: List[Dict], model: Optional[str], user_message: str, max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """Stream response."""
        full_response = ""
        client = self.nvidia_client
        temporary_client = client is None
        if temporary_client:
            client = NVIDIAClient()
            await client.__aenter__()
        try:
            async for chunk in client.chat_completion_stream(
                messages, model=model, max_tokens=max_tokens
            ):
                if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                    content = chunk["choices"][0]["delta"]["content"]
                    full_response += content
                    yield content
        finally:
            if temporary_client:
                await client.__aexit__(None, None, None)

        # Save to history
        assistant_msg = {
            "role": "assistant",
            "content": full_response,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversation_history.append(assistant_msg)

        # Save to memory
        if self.memory:
            asyncio.create_task(self._save_conversation(user_message, full_response))

    async def _save_conversation(self, user_message: str, assistant_message: str) -> None:
        """Persist chat without delaying the response sent to Ahmed."""
        try:
            if self.memory:
                await self.memory.add_conversation(
                    user_msg=user_message,
                    assistant_msg=assistant_message,
                )
        except Exception as exc:
            logger.warning("Could not persist conversation: %s", exc)

    async def chat_sync(self, message: str, **kwargs) -> str:
        """Synchronous chat for simple use cases."""
        return self.sync_client.chat_completion(
            messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": message}],
            **kwargs,
        )["choices"][0]["message"]["content"]

    # Voice methods
    async def transcribe_audio(self, audio_data: bytes, language: str = "en") -> str:
        """Transcribe audio to text."""
        async with NVIDIAClient() as client:
            result = await client.transcribe(audio_data, language=language)
            return result.get("text", "")

    async def synthesize_speech(self, text: str, voice: str = "female") -> bytes:
        """Convert text to speech."""
        async with NVIDIAClient() as client:
            return await client.synthesize(text, voice=voice)

    # Vision methods
    async def analyze_image(self, image_url: str, prompt: str) -> str:
        """Analyze image with vision model."""
        async with NVIDIAClient() as client:
            result = await client.vision(image_url, prompt)
            return result["choices"][0]["message"]["content"]

    # Memory methods
    async def remember(self, content: str, metadata: Optional[Dict] = None) -> str:
        """Store a memory."""
        if self.memory:
            return await self.memory.add(content, metadata)
        return ""

    async def recall(self, query: str, limit: int = 5) -> List[Dict]:
        """Search memories."""
        if self.memory:
            return await self.memory.search(query, limit)
        return []

    # Skill methods
    async def execute_skill(self, skill_name: str, params: Dict) -> Any:
        """Execute a specific skill."""
        return await self.skills.execute(skill_name, params, self)

    def get_available_skills(self) -> List[str]:
        """Get list of available skills."""
        return self.skills.list_skills()

    # System methods
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down JARVIS...")
        await self.swarm_runtime.shutdown()
        await self.agent_runtime.shutdown()
        if self.memory:
            await self.memory.close()
        if self.nvidia_client:
            await self.nvidia_client.__aexit__(None, None, None)
            self.nvidia_client = None
        await self._save_history()
        self._initialized = False

    def _require_runtime_effect(self, boundary: str) -> None:
        if self.control_service is None:
            return
        snapshot = self.control_service.snapshot()
        self.control_snapshot = snapshot
        if snapshot.state is not ControlState.RUNNING:
            raise ControlBlockedError(
                boundary=boundary,
                snapshot=snapshot,
            )

    async def _save_history(self):
        """Save conversation history."""
        if self.memory and self.conversation_history:
            await self.memory.save_conversation_history(self.conversation_history)

    def get_status(self) -> Dict:
        """Get system status."""
        return {
            "initialized": self._initialized,
            "nvidia_connected": self.nvidia_client is not None,
            "memory_connected": self.memory is not None and self.memory.is_connected,
            "skills_loaded": len(self.skills.list_skills()),
            "conversation_length": len(self.conversation_history),
            "agent_tools": len(self.agent_runtime.list_tools()),
            "agent_runs": len(self.agent_runtime.runs),
            "agent_runtime": self.agent_runtime.status(),
            "swarm_runtime": self.swarm_runtime.status(),
            "trust_status": self.trust_status,
            "control_state": (
                None if self.control_snapshot is None else self.control_snapshot.state.value
            ),
            "control_revision": (
                None if self.control_snapshot is None else self.control_snapshot.revision
            ),
            "timestamp": datetime.now().isoformat(),
        }


# Global instance
jarvis = Jarvis()
