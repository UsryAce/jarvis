"""News skill for Jarvis - fetch latest headlines by category/topic."""
import json
import logging
import os
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

CATEGORIES = {
    "general", "business", "entertainment", "health", "science", "sports", "technology"
}


class NewsSkill(Skill):
    name = "news"
    description = "Fetch latest news headlines by category or topic"
    triggers = ["news", "headlines", "latest news", "breaking news"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        category = params.get("category", self._detect_category(text))
        topic = params.get("topic", self._extract_topic(text, category))
        limit = params.get("limit", 5)

        api_key = os.environ.get("NEWS_API_KEY", "")
        if api_key:
            return await self._fetch_newsapi(category, topic, limit, api_key)
        else:
            return await self._fetch_rss(category, topic, limit)

    def _detect_category(self, text: str) -> str:
        for cat in CATEGORIES:
            if cat in text:
                return cat
        return "general"

    def _extract_topic(self, text: str, category: str) -> str:
        for cat in CATEGORIES:
            text = text.replace(cat, "")
        for w in ["news", "headlines", "latest", "breaking", "about", "for"]:
            text = text.replace(w, "")
        return text.strip() or ""

    async def _fetch_newsapi(self, category: str, topic: str, limit: int, api_key: str) -> str:
        try:
            if topic:
                url = f"https://newsapi.org/v2/everything?q={urllib.parse.quote(topic)}&pageSize={limit}&apiKey={api_key}"
            else:
                url = f"https://newsapi.org/v2/top-headlines?category={category}&pageSize={limit}&apiKey={api_key}"

            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            articles = data.get("articles", [])
            if not articles:
                return f"No news found for '{topic or category}'."

            results = []
            for a in articles[:limit]:
                title = a.get("title", "")
                source = a.get("source", {}).get("name", "")
                desc = a.get("description", "")
                results.append(f"**{title}** ({source})\n{desc}")

            header = f"News: {topic or category.title()}"
            return header + "\n\n" + "\n\n".join(results)
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return f"Failed to fetch news: {e}"

    async def _fetch_rss(self, category: str, topic: str, limit: int) -> str:
        try:
            sources = {
                "technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
                "business": "https://feeds.bbci.co.uk/news/business/rss.xml",
                "science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
                "health": "https://feeds.bbci.co.uk/news/health/rss.xml",
                "entertainment": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
                "sports": "https://feeds.bbci.co.uk/sport/rss.xml",
                "general": "https://feeds.bbci.co.uk/news/rss.xml",
            }

            import xml.etree.ElementTree as ET
            feed_url = sources.get(category, sources["general"])

            if topic:
                from urllib.request import urlopen, Request
                req = Request("https://news.google.com/rss/search", headers={"User-Agent": "Mozilla/5.0"})
                feed_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=en-US&gl=US&ceid=US:en"

            with urllib.request.urlopen(feed_url, timeout=10) as resp:
                xml_data = resp.read().decode("utf-8", errors="replace")

            root = ET.fromstring(xml_data)
            items = root.findall(".//item")[:limit]

            results = []
            for item in items:
                title = item.findtext("title", "")
                pub_date = item.findtext("pubDate", "")
                desc = item.findtext("description", "")
                if title:
                    results.append(f"**{title}**\n{pub_date}\n{desc}")

            if not results:
                return f"No news found for '{topic or category}'."
            return f"News: {topic or category.title()}\n\n" + "\n\n".join(results)
        except Exception as e:
            logger.error(f"RSS fetch error: {e}")
            return f"Failed to fetch news (try setting NEWS_API_KEY): {e}"
