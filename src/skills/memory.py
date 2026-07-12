"""Memory skill for Jarvis."""
from typing import Any, Dict

from src.skills.registry import Skill


class MemorySkill(Skill):
    """Memory management skill."""

    name = "memory"
    description = "Store, retrieve, and manage memories"
    triggers = ["remember", "recall", "forget", "memory", "memories"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Execute memory operations."""
        text = context.get("text", "").lower() if context else ""
        jarvis = context.get("jarvis") if context else None

        if not jarvis or not jarvis.memory:
            return "Memory system not available"

        if "remember" in text or "store" in text or "save" in text:
            content = params.get("content", self._extract_content(text, "remember"))
            if not content:
                return "What would you like me to remember?"
            memory_id = await jarvis.remember(content)
            return f"Remembered (ID: {memory_id[:8]}): {content[:100]}"

        elif "recall" in text or "search" in text or "find" in text:
            query = params.get("query", self._extract_content(text, "recall"))
            if not query:
                return "What would you like me to recall?"
            memories = await jarvis.recall(query, limit=5)
            if not memories:
                return f"No memories found for: {query}"
            results = []
            for m in memories:
                sim = m.get("similarity", 0)
                results.append(f"[{sim:.0%}] {m['content'][:200]}")
            return f"Found {len(memories)} memories:\n" + "\n".join(results)

        elif "forget" in text or "delete" in text:
            memory_id = params.get("memory_id", self._extract_id(text))
            if not memory_id:
                return "Which memory should I forget? Provide the ID."
            success = await jarvis.memory.delete(memory_id)
            return "Forgotten." if success else "Memory not found."

        elif "list" in text or "show" in text:
            stats = await jarvis.memory.get_stats()
            return f"Memory stats: {stats}"

        else:
            # Default: recall based on full text
            memories = await jarvis.recall(text, limit=3)
            if memories:
                return "Relevant memories:\n" + "\n".join(f"- {m['content'][:200]}" for m in memories)
            return "No relevant memories found."

    def _extract_content(self, text: str, keyword: str) -> str:
        """Extract content after keyword."""
        idx = text.find(keyword)
        if idx >= 0:
            return text[idx + len(keyword):].strip()
        return ""

    def _extract_id(self, text: str) -> str:
        """Extract memory ID from text."""
        import re
        match = re.search(r'[a-f0-9]{8,}', text)
        return match.group(0) if match else ""