"""Core Jarvis orchestrator."""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from pathlib import Path

from src.config import config
from src.clients.nvidia_client import NVIDIAClient, SyncNVIDIAClient
from src.memory.vector_memory import VectorMemory
from src.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class Jarvis:
    """Main Jarvis orchestrator."""

    def __init__(self):
        self.nvidia_client: Optional[NVIDIAClient] = None
        self.sync_client = SyncNVIDIAClient()
        self.memory: Optional[VectorMemory] = None
        self.skills = SkillRegistry()
        self.conversation_history: List[Dict] = []
        self.system_prompt = self._get_system_prompt()
        self._initialized = False

    def _get_system_prompt(self) -> str:
        """Get system prompt for Jarvis."""
        return """You are JARVIS, an advanced AI assistant inspired by the Iron Man AI system.
You are intelligent, helpful, witty, and professional.

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

        # Initialize NVIDIA client
        self.nvidia_client = NVIDIAClient()

        # Initialize memory
        self.memory = VectorMemory()
        await self.memory.initialize()

        # Load skills
        await self.skills.load_skills(config.get("skills.enabled", []))

        # Load conversation history
        await self._load_history()

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
    ) -> AsyncGenerator[str, None] | str:
        """Main chat interface."""
        if not self._initialized:
            await self.initialize()

        # Add user message to history
        user_msg = {"role": "user", "content": message, "timestamp": datetime.now().isoformat()}
        self.conversation_history.append(user_msg)

        # Retrieve relevant memories
        context = ""
        if use_memory and self.memory:
            memories = await self.memory.search(message, limit=5)
            if memories:
                context = "\nRelevant memories:\n" + "\n".join(
                    [f"- {m['content']}" for m in memories]
                )

        # Check for skill triggers
        skill_results = ""
        if use_skills:
            skill_results = await self.skills.execute_if_applicable(message, self)

        # Build messages
        system_content = self.system_prompt + context
        messages = [{"role": "system", "content": system_content}]
        
        # Include conversation history
        messages.extend(self.conversation_history[-20:])
        
        # Add skill results as a separate message if available
        if skill_results:
            messages.append({"role": "user", "content": f"[System: Tool results for your query]\n{skill_results}\n[End of tool results]"})
        
        # Add current user message
        messages.append({"role": "user", "content": message})

        # Get response
        if stream:
            return self._stream_response(messages, model)
        else:
            return await self._get_response(messages, model)

    async def _get_response(self, messages: List[Dict], model: Optional[str]) -> str:
        """Get non-streaming response."""
        async with NVIDIAClient() as client:
            response = await client.chat_completion(messages, model=model)
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
            await self.memory.add_conversation(user_msg=messages[-1]["content"], assistant_msg=content)

        return content

    async def _stream_response(
        self, messages: List[Dict], model: Optional[str]
    ) -> AsyncGenerator[str, None]:
        """Stream response."""
        full_response = ""
        async with NVIDIAClient() as client:
            async for chunk in client.chat_completion_stream(messages, model=model):
                if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                    content = chunk["choices"][0]["delta"]["content"]
                    full_response += content
                    yield content

        # Save to history
        assistant_msg = {
            "role": "assistant",
            "content": full_response,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversation_history.append(assistant_msg)

        # Save to memory
        if self.memory:
            await self.memory.add_conversation(
                user_msg=messages[-1]["content"], assistant_msg=full_response
            )

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
        if self.memory:
            await self.memory.close()
        await self._save_history()
        self._initialized = False

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
            "timestamp": datetime.now().isoformat(),
        }


# Global instance
jarvis = Jarvis()