"""Search skill for Jarvis - web search with multiple backends."""
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)


class SearchSkill(Skill):
    name = "search"
    description = "Search the web using multiple backends (Google, DuckDuckGo, fallback)"
    triggers = ["search", "google", "look up", "find online", "search for"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        query = params.get("query", self._extract_query(text))

        if not query:
            return "What should I search for?"

        api_key = os.environ.get("SEARCH_API_KEY", "")
        cx = os.environ.get("SEARCH_CX", "")

        if api_key and cx:
            return await self._google_search(query, api_key, cx)
        return await self._duckduckgo_search(query)

    def _extract_query(self, text: str) -> str:
        for t in ["search for", "search", "google", "look up", "find online", "find"]:
            idx = text.find(t)
            if idx >= 0:
                return text[idx + len(t):].strip().strip("'\"").strip()
        return text.strip()

    async def _google_search(self, query: str, api_key: str, cx: str) -> str:
        url = "https://www.googleapis.com/customsearch/v1"
        params = urllib.parse.urlencode({"key": api_key, "cx": cx, "q": query, "num": 5})
        full_url = f"{url}?{params}"

        try:
            with urllib.request.urlopen(full_url, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            items = data.get("items", [])
            if not items:
                return f"No results for: {query}"

            results = []
            for item in items[:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                results.append(f"**{title}**\n{snippet}\n{link}")

            return f"Search results for '{query}':\n\n" + "\n\n".join(results)
        except Exception as e:
            logger.error(f"Google search failed, falling back: {e}")
            return await self._duckduckgo_search(query)

    async def _duckduckgo_search(self, query: str) -> str:
        try:
            url = "https://html.duckduckgo.com/html/"
            data = urllib.parse.urlencode({"q": query}).encode()
            req = urllib.request.Request(url, data=data,
                                         headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            results = []
            for match in re.finditer(
                r'class="result__title".*?<a[^>]*>(.*?)</a>.*?class="result__snippet">(.*?)</a>',
                html, re.DOTALL
            ):
                title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                snippet = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                if title:
                    results.append(f"**{title}**\n{snippet}")

            if not results:
                return await self._fallback_search(query)
            return f"Search results for '{query}':\n\n" + "\n\n".join(results[:5])
        except Exception as e:
            logger.error(f"DuckDuckGo failed: {e}")
            return await self._fallback_search(query)

    async def _fallback_search(self, query: str) -> str:
        try:
            url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            results = []
            for match in re.finditer(r'<a[^>]+class="result-link"[^>]*>(.*?)</a>', html):
                title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                if title and title not in results:
                    results.append(f"**{title}**")

            if not results:
                return f"No results found for: {query}"
            return f"Search results for '{query}':\n\n" + "\n\n".join(results[:5])
        except Exception as e:
            return f"Search error: {e}"
