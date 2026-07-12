"""Web search skill for Jarvis."""
import aiohttp
import json
from typing import Any, Dict

from src.skills.registry import Skill
from src.config import config


class WebSearchSkill(Skill):
    """Web search skill using Google Custom Search or DuckDuckGo."""

    name = "web_search"
    description = "Search the web for information"
    triggers = ["search", "google", "look up", "find", "what is", "who is", "how to"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Execute web search."""
        text = context.get("text", "") if context else ""
        query = params.get("query", self._extract_query(text))

        if not query:
            return "What would you like me to search for?"

        # Try Google Custom Search first
        api_key = config.get("external_apis.search")
        cx = config.get("external_apis.search_cx")

        if api_key and cx:
            return await self._google_search(query, api_key, cx)
        else:
            return await self._duckduckgo_search(query)

    def _extract_query(self, text: str) -> str:
        """Extract search query from text."""
        import re
        # Remove trigger words
        text = re.sub(r'\b(search|google|look up|find|what is|who is|how to)\b', '', text, flags=re.IGNORECASE)
        return text.strip()

    async def _google_search(self, query: str, api_key: str, cx: str) -> str:
        """Search using Google Custom Search API."""
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": 5,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()

            if "items" not in data:
                return f"No results found for: {query}"

            results = []
            for item in data["items"][:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                results.append(f"**{title}**\n{snippet}\n{link}")

            return f"Search results for '{query}':\n\n" + "\n\n".join(results)

        except Exception as e:
            return f"Google search error: {e}"

    async def _duckduckgo_search(self, query: str) -> str:
        """Search using DuckDuckGo HTML scrape."""
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params) as response:
                    html = await response.text()

            # Parse results (simple regex)
            import re
            results = []
            for match in re.finditer(r'class="result__title">.*?<a[^>]*>(.*?)</a>.*?class="result__snippet">(.*?)</a>', html, re.DOTALL):
                title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                snippet = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                if title and snippet:
                    results.append(f"**{title}**\n{snippet}")

            if not results:
                return f"No results found for: {query}"

            return f"Search results for '{query}':\n\n" + "\n\n".join(results[:5])

        except Exception as e:
            return f"DuckDuckGo search error: {e}"