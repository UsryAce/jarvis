"""Knowledge skill for Jarvis - internal knowledge base, Wikipedia, quick facts."""
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
KNOWLEDGE_DB = DATA_DIR / "knowledge.json"


FACTS_DB = {
    "speed of light": "299,792,458 meters per second",
    "speed of sound": "343 meters per second at sea level",
    "gravity": "9.80665 m/s² on Earth's surface",
    "population of earth": "Approximately 8.1 billion (2024 estimate)",
    "distance to moon": "Approximately 384,400 kilometers",
    "distance to sun": "Approximately 149.6 million kilometers",
    "boiling point of water": "100°C (212°F) at sea level",
    "freezing point of water": "0°C (32°F) at sea level",
    "largest planet": "Jupiter is the largest planet in our solar system",
    "smallest planet": "Mercury is the smallest planet in our solar system",
    "capital of france": "Paris",
    "capital of japan": "Tokyo",
    "capital of germany": "Berlin",
    "capital of italy": "Rome",
    "capital of spain": "Madrid",
    "capital of australia": "Canberra",
    "capital of india": "New Delhi",
    "capital of china": "Beijing",
    "capital of russia": "Moscow",
    "capital of united kingdom": "London",
    "capital of canada": "Ottawa",
    "capital of brazil": "Brasília",
    "capital of egypt": "Cairo",
    "height of mount everest": "8,848.86 meters (29,031.7 feet)",
    "height of eiffel tower": "330 meters (1,083 feet)",
    "depth of mariana trench": "Approximately 11,034 meters",
    "area of earth": "510.1 million square kilometers",
    "largest ocean": "Pacific Ocean",
    "largest desert": "Antarctic Desert",
    "largest country": "Russia is the largest country by area",
    "most populous country": "India is the most populous country",
    "most spoken language": "English by total speakers, Mandarin Chinese by native speakers",
}


class KnowledgeSkill(Skill):
    name = "knowledge"
    description = "Query internal knowledge base, Wikipedia, and quick facts"
    triggers = ["what is", "who is", "tell me about", "define", "explain", "knowledge", "how does", "why is"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        query = params.get("query", self._extract_query(text))

        if not query:
            return "What would you like to know? Example: what is the speed of light"

        result = self._check_facts(query)
        if result:
            return result

        result = self._check_internal(query)
        if result:
            return result

        return await self._fetch_wikipedia(query)

    def _extract_query(self, text: str) -> str:
        for t in ["tell me about", "what is", "who is", "explain", "define", "how does", "why is", "knowledge about"]:
            idx = text.find(t)
            if idx >= 0:
                return text[idx + len(t):].strip().strip("?").strip()
        return text.strip().strip("?").strip()

    def _check_facts(self, query: str) -> Optional[str]:
        q = query.lower().strip()
        for key, value in FACTS_DB.items():
            if key in q or q in key:
                return f"{key.title()}: {value}"
        return None

    def _check_internal(self, query: str) -> Optional[str]:
        try:
            if not Path(KNOWLEDGE_DB).exists():
                return None
            entries = json.loads(Path(KNOWLEDGE_DB).read_text(encoding="utf-8"))
            q = query.lower()
            for entry in entries:
                if q in entry.get("question", "").lower() or q in entry.get("answer", "").lower():
                    return entry["answer"]
            return None
        except Exception:
            return None

    async def _fetch_wikipedia(self, query: str) -> str:
        try:
            search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query.replace(' ', '_'))}"
            req = urllib.request.Request(search_url, headers={"User-Agent": "Jarvis/1.0"})

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            if data.get("type") == "disambiguation":
                return f"'{query}' may refer to multiple things. Please be more specific."

            title = data.get("title", query.title())
            extract = data.get("extract", "")
            url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

            if not extract:
                return f"No Wikipedia entry found for: {query}"

            if len(extract) > 500:
                extract = extract[:500] + "..."

            result = f"**{title}**\n{extract}"
            if url:
                result += f"\n\nSource: {url}"
            return result

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return f"I don't know about '{query}' yet. Try adding it to my knowledge base."
            return f"Wikipedia lookup failed: {e}"
        except Exception as e:
            logger.error(f"Wikipedia error: {e}")
            return f"Sorry, I couldn't find information about '{query}'."
